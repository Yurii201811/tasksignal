import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import routes
from app.db.session import engine
from app.models.all_models import ResearchProject, Source
from app.schemas.api import ItemOut, OpportunityOut


def test_health(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cors_preflight_allows_configured_frontend_origin(client) -> None:
    response = client.options(
        "/api/readiness",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_process_demo_endpoint(client) -> None:
    response = client.post("/api/process/demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_items_loaded"] >= 17
    assert payload["signals_detected"] >= 15
    assert payload["opportunities_created"] >= 5

    opportunities = client.get("/api/opportunities").json()
    assert len(opportunities) >= 5
    assert opportunities[0]["generated_prompt"].startswith("# Build")
    assert opportunities[0]["scoring_breakdown_json"]["rank_drivers"]
    assert opportunities[0]["evidence_items"][0]["evidence_spans"]
    assert "Ranking rationale" in opportunities[0]["generated_prompt"]
    assert opportunities[0]["review_state"] == "new"
    assert opportunities[0]["review_note"] is None
    assert opportunities[0]["decision_updated_at"] is None


def test_hosted_write_protection_requires_the_operator_token(client, monkeypatch) -> None:
    from app import main as app_main

    monkeypatch.setattr(
        app_main,
        "settings",
        SimpleNamespace(
            require_operator_token_for_all_api=False,
            require_operator_token_for_writes=True,
            operator_scan_token="hosted-operator-token",
            llm_provider=routes.settings.llm_provider,
            embedding_model=routes.settings.embedding_model,
        ),
    )

    assert client.get("/api/stats").status_code == 200

    missing = client.post(
        "/api/process/demo",
        headers={"Origin": "http://localhost:3000"},
    )
    assert missing.status_code == 403
    assert missing.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert missing.json() == {"detail": "Hosted writes require a valid X-Operator-Scan-Token."}

    invalid = client.post(
        "/api/process/demo",
        headers={"X-Operator-Scan-Token": "wrong-token"},
    )
    assert invalid.status_code == 403

    allowed = client.post(
        "/api/process/demo",
        headers={"X-Operator-Scan-Token": "hosted-operator-token"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["raw_items_loaded"] >= 17


def test_hosted_api_protection_covers_reads_and_handles_non_ascii_tokens(
    client, monkeypatch
) -> None:
    from app import main as app_main

    monkeypatch.setattr(
        app_main,
        "settings",
        SimpleNamespace(
            require_operator_token_for_all_api=True,
            require_operator_token_for_writes=True,
            operator_scan_token="hosted-operator-token",
            llm_provider=routes.settings.llm_provider,
            embedding_model=routes.settings.embedding_model,
        ),
    )

    assert client.get("/health").status_code == 200
    assert (
        client.options(
            "/api/stats",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Operator-Scan-Token",
            },
        ).status_code
        == 200
    )

    missing = client.get("/api/stats", headers={"Origin": "http://localhost:3000"})
    assert missing.status_code == 403
    assert missing.headers["access-control-allow-origin"] == "http://localhost:3000"

    allowed = client.get(
        "/api/stats",
        headers={"X-Operator-Scan-Token": "hosted-operator-token"},
    )
    assert allowed.status_code == 200

    assert app_main.operator_token_matches("\u00ff", "hosted-operator-token") is False


def test_integrations_report_status_without_secret_values(client, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "github_token", "ghp_do_not_leak")

    response = client.get("/api/integrations")

    assert response.status_code == 200
    text = json.dumps(response.json())
    assert "ghp_do_not_leak" not in text
    github = next(item for item in response.json() if item["id"] == "github")
    assert github["credential_state"] == "configured"
    assert "GITHUB_TOKEN" in github["optional_env"]


def test_readiness_reports_workspace_state_without_secret_values(client, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "operator_scan_token", "do-not-leak")

    response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["ready_sources"]
    assert payload["checks"]["codex_task_packs"] is True
    assert payload["checks"]["operator_scan_token_configured"] is True
    assert "do-not-leak" not in json.dumps(payload)


def test_readiness_warns_when_public_scan_sources_exclude_browser_safe_sources(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(routes.settings, "public_scan_sources", "github,reddit")

    response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checks"]["public_scan_sources"] == []
    assert payload["checks"]["public_scan_sources_configured"] is False
    assert any("browser-safe source" in warning for warning in payload["warnings"])
    assert "github" not in json.dumps(payload["checks"]["public_scan_sources"])


def test_readiness_warns_when_author_hash_salt_uses_default(client, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "author_hash_salt", "change-me")

    response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checks"]["author_hash_salt_custom"] is False
    assert any("AUTHOR_HASH_SALT" in warning for warning in payload["warnings"])
    assert "change-me" not in json.dumps(payload)


def test_readiness_reports_custom_author_hash_salt_without_secret_value(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(routes.settings, "author_hash_salt", "do-not-leak")

    response = client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checks"]["author_hash_salt_custom"] is True
    assert "do-not-leak" not in json.dumps(payload)


def test_sources_redact_stored_config_values(client) -> None:
    with Session(engine) as session:
        session.add(
            Source(
                name="Configured GitHub",
                type="github",
                config_json={
                    "owner": "public-org",
                    "api_key": "do-not-leak",
                    "nested": {"access_token": "also-secret"},
                },
                enabled=True,
            )
        )
        session.commit()

    response = client.get("/api/sources")

    assert response.status_code == 200
    text = json.dumps(response.json())
    assert "do-not-leak" not in text
    assert "also-secret" not in text
    configured = next(item for item in response.json() if item["name"] == "Configured GitHub")
    assert configured["config_json"] == {}


def test_source_registry_mutations_require_operator_token(client, monkeypatch) -> None:
    payload = {
        "name": "Custom HN",
        "type": "hackernews",
        "config_json": {"feed": "ask"},
        "enabled": True,
    }

    response = client.post("/api/sources", json=payload)

    assert response.status_code == 403
    assert "OPERATOR_SCAN_TOKEN" in response.json()["detail"]

    monkeypatch.setattr(routes.settings, "operator_scan_token", "test-operator-token")
    missing_token = client.post("/api/sources", json=payload)
    bad_token = client.post(
        "/api/sources",
        headers={"X-Operator-Scan-Token": "wrong"},
        json=payload,
    )
    created = client.post(
        "/api/sources",
        headers={"X-Operator-Scan-Token": "test-operator-token"},
        json=payload,
    )

    assert missing_token.status_code == 403
    assert bad_token.status_code == 403
    assert created.status_code == 200
    assert created.json()["name"] == "Custom HN"
    assert created.json()["config_json"] == {}

    source_id = created.json()["id"]
    delete_without_token = client.delete(f"/api/sources/{source_id}")
    delete_with_token = client.delete(
        f"/api/sources/{source_id}",
        headers={"X-Operator-Scan-Token": "test-operator-token"},
    )

    assert delete_without_token.status_code == 403
    assert delete_with_token.status_code == 200


def test_source_registry_rejects_secret_like_config_keys(client, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "operator_scan_token", "test-operator-token")

    response = client.post(
        "/api/sources",
        headers={"X-Operator-Scan-Token": "test-operator-token"},
        json={
            "name": "Unsafe source config",
            "type": "github",
            "config_json": {
                "filters": {"access_token": "do-not-leak"},
                "display": "public",
            },
            "enabled": True,
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "environment variables" in detail
    assert "config_json.filters.access_token" in detail
    assert "do-not-leak" not in detail


def test_local_workspace_can_store_single_user_defaults(client) -> None:
    initial = client.get("/api/local-workspace")

    assert initial.status_code == 200
    assert initial.json()["id"] == 1
    assert initial.json()["configured"] is False
    assert initial.json()["default_source_type"] == "hackernews"

    response = client.patch(
        "/api/local-workspace",
        json={
            "owner_name": "Local Builder",
            "workspace_goal": "Find concrete developer-tool ideas",
            "default_source_type": "fixture",
            "default_query": "",
            "default_limit": 20,
            "default_cadence": "daily",
            "default_schedule_interval_hours": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["owner_name"] == "Local Builder"
    assert payload["workspace_goal"] == "Find concrete developer-tool ideas"
    assert payload["default_source_type"] == "fixture"
    assert payload["default_limit"] == 20
    assert payload["default_cadence"] == "daily"

    readiness = client.get("/api/readiness").json()
    assert readiness["checks"]["local_workspace_configured"] is True
    assert "Set the local workspace owner" not in " ".join(readiness["warnings"])


def test_local_workspace_rejects_unknown_default_source(client) -> None:
    response = client.patch(
        "/api/local-workspace",
        json={
            "owner_name": "Local Builder",
            "workspace_goal": "Find ideas",
            "default_source_type": "unknown",
            "default_query": "",
            "default_limit": 20,
            "default_cadence": "manual",
            "default_schedule_interval_hours": None,
        },
    )

    assert response.status_code == 400
    assert "Unsupported source" in response.json()["detail"]


def test_research_project_can_save_and_run_fixture_workflow(client) -> None:
    create_response = client.post(
        "/api/research-projects",
        json={
            "name": "Fixture opportunity review",
            "description": "Repeatable fixture scan for agent handoff checks.",
            "source_type": "fixture",
            "query": "",
            "limit": 20,
            "cadence": "daily",
            "labels": ["fixture", "codex"],
            "enabled": True,
        },
    )

    assert create_response.status_code == 200
    project = create_response.json()
    assert project["source_type"] == "fixture"
    assert project["labels"] == ["fixture", "codex"]
    assert project["cadence"] == "daily"
    assert project["next_run_at"] is not None
    assert project["run_count"] == 0

    run_response = client.post(f"/api/research-projects/{project['id']}/run")

    assert run_response.status_code == 200
    scan = run_response.json()
    assert scan["source_type"] == "fixture"
    assert scan["status"] == "completed"
    assert scan["items_found"] >= 17

    projects = client.get("/api/research-projects").json()
    saved = next(item for item in projects if item["id"] == project["id"])
    assert saved["last_scan_id"] == scan["id"]
    assert saved["last_scan_status"] == "completed"
    assert saved["last_run_at"] is not None
    assert saved["next_run_at"] is not None
    assert saved["run_count"] == 1


def test_due_research_project_run_advances_schedule(client) -> None:
    create_response = client.post(
        "/api/research-projects",
        json={
            "name": "Due fixture project",
            "source_type": "fixture",
            "query": "",
            "limit": 20,
            "cadence": "custom",
            "schedule_interval_hours": 1,
            "labels": [],
            "enabled": True,
        },
    )
    project_id = create_response.json()["id"]
    with Session(engine) as session:
        project = session.scalars(
            select(ResearchProject).where(ResearchProject.id == UUID(project_id))
        ).one()
        project.next_run_at = datetime(2026, 6, 3, tzinfo=UTC)
        session.commit()

    response = client.post("/api/research-projects/run-due")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ran"] == 1
    assert payload["skipped"] == 0
    assert payload["scans"][0]["status"] == "completed"

    saved = client.get(f"/api/research-projects/{project_id}").json()
    assert saved["last_scan_status"] == "completed"
    assert saved["schedule_interval_hours"] == 1
    assert saved["last_run_at"] is not None
    assert saved["next_run_at"] is not None
    assert saved["run_count"] == 1


def test_due_credentialed_research_project_skips_without_operator_token(client) -> None:
    create_response = client.post(
        "/api/research-projects",
        json={
            "name": "Due GitHub project",
            "source_type": "github",
            "query": "label:bug",
            "limit": 5,
            "cadence": "custom",
            "schedule_interval_hours": 1,
            "labels": [],
            "enabled": True,
        },
    )
    project_id = create_response.json()["id"]
    with Session(engine) as session:
        project = session.scalars(
            select(ResearchProject).where(ResearchProject.id == UUID(project_id))
        ).one()
        project.next_run_at = datetime(2026, 6, 3, tzinfo=UTC)
        session.commit()

    response = client.post("/api/research-projects/run-due")

    assert response.status_code == 200
    assert response.json()["ran"] == 0
    assert response.json()["skipped"] == 1


def test_credentialed_research_project_run_requires_operator_token(client) -> None:
    create_response = client.post(
        "/api/research-projects",
        json={
            "name": "GitHub project",
            "source_type": "github",
            "query": "label:bug",
            "limit": 5,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    project = create_response.json()

    run_response = client.post(f"/api/research-projects/{project['id']}/run")

    assert run_response.status_code == 403
    assert "X-Operator-Scan-Token" in run_response.json()["detail"]


def test_public_scan_error_is_clear_when_no_public_scan_sources_are_enabled(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(routes.settings, "public_scan_sources", "github")

    response = client.post(
        "/api/scans",
        json={"source": "hackernews", "query": "ask", "limit": 10},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert "Allowed public scan sources: none" in detail
    assert "PUBLIC_SCAN_SOURCES" in detail
    assert "browser-safe source" in detail


def test_process_demo_reuses_evidence_while_creating_a_fresh_scan_snapshot(client) -> None:
    first = client.post("/api/process/demo").json()
    second = client.post("/api/process/demo").json()

    assert first["normalized_items_created"] >= 17
    assert first["opportunities_created"] >= 5
    assert second["raw_items_loaded"] >= 17
    assert second["normalized_items_created"] == 0
    assert second["signals_detected"] == first["signals_detected"]
    assert second["opportunities_created"] == first["opportunities_created"]
    assert len(client.get("/api/opportunities").json()) >= 5
    assert client.get("/api/stats").json()["problem_signals"] == first["signals_detected"]


def test_process_demo_reset_rejects_when_token_not_configured(client) -> None:
    response = client.post("/api/process/demo?reset=true")

    assert response.status_code == 403
    assert "Demo reset requires" in response.json()["detail"]


def test_process_demo_reset_requires_token_when_configured(client, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "demo_reset_token", "test-reset-token")

    response = client.post("/api/process/demo?reset=true")

    assert response.status_code == 403
    assert "Demo reset requires" in response.json()["detail"]


def test_process_demo_reset_accepts_configured_token(client, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "demo_reset_token", "test-reset-token")

    response = client.post(
        "/api/process/demo?reset=true",
        headers={"X-Demo-Reset-Token": "test-reset-token"},
    )

    assert response.status_code == 200
    assert response.json()["opportunities_created"] >= 5


def test_regenerate_opportunity_rebuilds_prompt_from_evidence(client) -> None:
    client.post("/api/process/demo")
    opportunity = client.get("/api/opportunities").json()[0]

    response = client.post(f"/api/opportunities/{opportunity['id']}/regenerate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == opportunity["id"]
    assert payload["updated_at"] >= opportunity["updated_at"]
    assert payload["generated_prompt"].startswith("# Build")
    assert "Top source excerpts" in payload["generated_prompt"]
    assert payload["scoring_breakdown_json"]["common_phrases"]
    assert payload["problem_statement"].count("People repeatedly describe") == 1


def test_prompt_enhancement_requires_configured_runtime(client, monkeypatch) -> None:
    client.post("/api/process/demo")
    opportunity = client.get("/api/opportunities").json()[0]
    monkeypatch.setattr(routes.settings, "operator_scan_token", "test-operator-token")

    response = client.post(
        f"/api/opportunities/{opportunity['id']}/enhance",
        headers={"X-Operator-Scan-Token": "test-operator-token"},
    )

    assert response.status_code == 409
    assert "LLM_PROVIDER" in response.json()["detail"]


def test_prompt_enhancement_requires_operator_token(client, monkeypatch) -> None:
    client.post("/api/process/demo")
    opportunity = client.get("/api/opportunities").json()[0]
    monkeypatch.setattr(routes.settings, "operator_scan_token", "test-operator-token")

    missing_token = client.post(f"/api/opportunities/{opportunity['id']}/enhance")
    bad_token = client.post(
        f"/api/opportunities/{opportunity['id']}/enhance",
        headers={"X-Operator-Scan-Token": "wrong"},
    )

    assert missing_token.status_code == 403
    assert "X-Operator-Scan-Token" in missing_token.json()["detail"]
    assert bad_token.status_code == 403
    assert "X-Operator-Scan-Token" in bad_token.json()["detail"]


def test_prompt_enhancement_can_apply_generated_prompt(client, monkeypatch) -> None:
    client.post("/api/process/demo")
    opportunity = client.get("/api/opportunities").json()[0]

    def fake_enhance(prompt: str) -> tuple[str, str, str]:
        return "openai", "test-model", f"{prompt}\n\n## Implementation Checklist\n- Verify."

    monkeypatch.setattr(routes.settings, "operator_scan_token", "test-operator-token")
    monkeypatch.setattr(routes, "enhance_prompt", fake_enhance)

    response = client.post(
        f"/api/opportunities/{opportunity['id']}/enhance?apply=true",
        headers={"X-Operator-Scan-Token": "test-operator-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["model"] == "test-model"
    assert payload["applied"] is True
    assert "Implementation Checklist" in payload["enhanced_prompt"]

    saved = client.get(f"/api/opportunities/{opportunity['id']}/prompt").json()
    assert saved["prompt"] == payload["enhanced_prompt"]


def test_evidence_bundle_export_includes_visible_evidence_without_authors(client) -> None:
    client.post("/api/process/demo")
    opportunity = client.get("/api/opportunities").json()[0]
    evidence_item = opportunity["evidence_items"][0]

    response = client.get(f"/api/opportunities/{opportunity['id']}/evidence.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert f"evidence-{opportunity['id']}.md" in response.headers["content-disposition"]
    text = response.text
    assert text.startswith("# Evidence Bundle:")
    assert opportunity["title"] in text
    assert opportunity["problem_statement"] in text
    assert "## Score Breakdown" in text
    assert "## Evidence Items" in text
    assert evidence_item["title"] in text
    assert evidence_item["evidence_spans"][0] in text
    assert evidence_item["url"] in text
    assert f"/api/opportunities/{opportunity['id']}/prompt" in text
    assert "author_hash" not in text
    assert "raw_author" not in text
    assert "contributor-a" not in text
    assert "hn_builder" not in text
    assert "frontend_builder_41" not in text


def test_task_pack_exports_codex_ready_markdown_and_json(client) -> None:
    client.post("/api/process/demo")
    opportunity = client.get("/api/opportunities").json()[0]

    markdown_response = client.get(f"/api/opportunities/{opportunity['id']}/task-pack.md")
    json_response = client.get(f"/api/opportunities/{opportunity['id']}/task-pack.json")

    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-type"].startswith("text/markdown")
    text = markdown_response.text
    assert text.startswith("# TaskSignal Codex Task Pack:")
    assert "## Acceptance Criteria" in text
    assert "## Privacy And Safety Constraints" in text
    assert "## Generated Build Prompt" in text
    assert opportunity["title"] in text
    assert "raw_author" not in text

    assert json_response.status_code == 200
    payload = json_response.json()
    assert payload["opportunity_id"] == opportunity["id"]
    assert payload["acceptance_criteria"]
    assert payload["privacy_constraints"]
    assert payload["markdown"] == text


def test_prompt_markdown_export_remains_generated_prompt(client) -> None:
    client.post("/api/process/demo")
    opportunity = client.get("/api/opportunities").json()[0]

    response = client.get(f"/api/opportunities/{opportunity['id']}/export.md")

    assert response.status_code == 200
    assert response.text == opportunity["generated_prompt"]


def test_evidence_bundle_export_drops_unsafe_source_urls() -> None:
    now = datetime(2026, 6, 3, tzinfo=UTC)
    opportunity = OpportunityOut(
        id=uuid4(),
        cluster_id=uuid4(),
        title="Unsafe source URL test",
        problem_statement="People need evidence exports.",
        target_user="Maintainers",
        current_workaround="Manual review",
        suggested_mvp="Evidence bundle",
        why_now="Reviewers need traceability.",
        feasibility_score=0.8,
        opportunity_score=0.7,
        competition_notes="Focused export scope.",
        scoring_breakdown_json={"frequency": 1.0},
        generated_prompt="# Build test",
        review_state="new",
        review_note=None,
        decision_updated_at=None,
        created_at=now,
        updated_at=now,
        evidence_items=[
            ItemOut(
                id=uuid4(),
                source="github",
                external_id="unsafe-url",
                url="javascript:alert(1)",
                title="Unsafe URL should not be exported",
                body="Evidence body.",
                score=None,
                comments_count=None,
                created_at=now,
                tags=[],
                signal_type="manual_workflow",
                pain_score=0.5,
                task_concreteness_score=0.6,
                buying_intent_score=0.1,
                evidence_spans=["Evidence body."],
            )
        ],
        signal_count=1,
        top_source="github",
        evidence_readiness={
            "level": "weak",
            "evidence_count": 1,
            "source_count": 1,
            "safe_url_count": 0,
            "reviewed_count": 0,
            "source_url_coverage": 0.0,
            "human_review_coverage": 0.0,
            "checks": {
                "enough_evidence": False,
                "source_diversity": False,
                "source_url_coverage": False,
                "human_review_coverage": False,
            },
            "passed_checks": [],
            "gaps": [
                "Collect 4 more evidence items.",
                "Add evidence from 1 more source.",
                "Increase safe source URL coverage to at least 80%.",
                "Review 1 more evidence item.",
            ],
        },
    )

    text = routes.evidence_bundle_markdown(opportunity)

    assert "javascript:alert" not in text
    assert "No source URL stored" in text
