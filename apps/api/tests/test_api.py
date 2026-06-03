import json
from datetime import UTC, datetime
from uuid import uuid4

from app.api import routes
from app.schemas.api import ItemOut, OpportunityOut


def test_health(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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


def test_integrations_report_status_without_secret_values(client, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "github_token", "ghp_do_not_leak")

    response = client.get("/api/integrations")

    assert response.status_code == 200
    text = json.dumps(response.json())
    assert "ghp_do_not_leak" not in text
    github = next(item for item in response.json() if item["id"] == "github")
    assert github["credential_state"] == "configured"
    assert "GITHUB_TOKEN" in github["optional_env"]


def test_research_project_can_save_and_run_fixture_workflow(client) -> None:
    create_response = client.post(
        "/api/research-projects",
        json={
            "name": "Fixture opportunity review",
            "description": "Repeatable fixture scan for agent handoff checks.",
            "source_type": "fixture",
            "query": "",
            "limit": 20,
            "cadence": "manual",
            "labels": ["fixture", "codex"],
            "enabled": True,
        },
    )

    assert create_response.status_code == 200
    project = create_response.json()
    assert project["source_type"] == "fixture"
    assert project["labels"] == ["fixture", "codex"]

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


def test_process_demo_is_idempotent_without_reset(client) -> None:
    first = client.post("/api/process/demo").json()
    second = client.post("/api/process/demo").json()

    assert first["normalized_items_created"] >= 17
    assert first["opportunities_created"] >= 5
    assert second["raw_items_loaded"] >= 17
    assert second["normalized_items_created"] == 0
    assert second["opportunities_created"] == 0
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
    )

    text = routes.evidence_bundle_markdown(opportunity)

    assert "javascript:alert" not in text
    assert "No source URL stored" in text
