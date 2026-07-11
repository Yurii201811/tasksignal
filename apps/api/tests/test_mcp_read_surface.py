from __future__ import annotations

import json
from urllib.parse import quote
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.session import engine
from app.services.mcp_surface.reads import (
    McpReadError,
    compare_project_runs,
    get_build_packet,
    get_evaluation,
    get_opportunity_thread,
    list_project_runs,
    list_projects,
    list_resource_templates,
    list_resources,
    resolve_resource,
    search_opportunities,
    verify_build_packet,
)

FORBIDDEN_KEYS = {
    "author_hash",
    "config_json",
    "credentials",
    "details_json",
    "raw_json",
    "review_note",
    "secret_hash",
    "source_snapshot_json",
    "user_note",
}


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested_key for nested in value.values() for nested_key in _all_keys(nested)
        }
    if isinstance(value, list):
        return {nested_key for nested in value for nested_key in _all_keys(nested)}
    return set()


def _fixture_packet(client) -> tuple[dict, dict, dict]:
    project_response = client.post(
        "/api/v1/research-projects",
        json={
            "name": "MCP read surface",
            "description": "Public evidence read tests.",
            "source_type": "fixture",
            "query": "",
            "limit": 100,
            "cadence": "manual",
            "labels": ["mcp"],
            "enabled": True,
        },
    )
    assert project_response.status_code == 200, project_response.text
    project = project_response.json()
    run_response = client.post(f"/api/v1/research-projects/{project['id']}/run")
    assert run_response.status_code == 200, run_response.text
    run = client.get(f"/api/v1/research-projects/{project['id']}/runs").json()[0]
    thread = client.get(f"/api/v1/opportunity-threads?project_id={project['id']}").json()[0]
    updated = client.patch(
        f"/api/v1/opportunity-threads/{thread['id']}/decision",
        json={
            "review_state": "build_candidate",
            "review_note": "LOCAL-MCP-THREAD-NOTE-MUST-STAY-PRIVATE",
            "expected_version": thread["version"],
        },
    )
    assert updated.status_code == 200, updated.text
    thread = updated.json()
    evidence = thread["current_snapshot"]["evidence_items"]
    label = client.post(
        "/api/v1/labels",
        json={
            "item_id": evidence[0]["id"],
            "label": "true_signal",
            "user_note": "LOCAL-MCP-EVIDENCE-NOTE-MUST-STAY-PRIVATE",
        },
    )
    assert label.status_code == 200, label.text
    packet_response = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={},
    )
    assert packet_response.status_code == 201, packet_response.text
    return project, run, packet_response.json()


def test_read_tools_are_json_serializable_and_redacted(client) -> None:
    project, run, packet = _fixture_packet(client)

    with Session(engine) as db:
        projects = list_projects(db)
        runs = list_project_runs(db, project["id"])
        delta = compare_project_runs(db, project["id"], run["id"])
        search = search_opportunities(
            db,
            query="manual workflow pain",
            limit=10,
            project_id=project["id"],
        )
        thread = get_opportunity_thread(db, packet["thread_id"])
        evaluation = get_evaluation(db)
        fetched_packet = get_build_packet(db, packet["id"])
        verification = verify_build_packet(db, packet["id"])

    payload = {
        "projects": projects,
        "runs": runs,
        "delta": delta,
        "search": search,
        "thread": thread,
        "evaluation": evaluation,
        "packet": fetched_packet,
        "verification": verification,
    }
    serialized = json.dumps(payload, sort_keys=True)
    assert projects[0]["id"] == project["id"]
    assert runs[0]["id"] == run["id"]
    assert delta["run_id"] == run["id"]
    assert search["evidence_hits"]
    assert search["opportunity_threads"]
    assert thread["id"] == packet["thread_id"]
    assert thread["current_snapshot"]["evidence_items"][0]["untrusted_evidence"] is True
    assert evaluation["total_reviewable_items"] >= 1
    assert fetched_packet["id"] == packet["id"]
    assert verification["valid"] is True
    assert not (_all_keys(payload) & FORBIDDEN_KEYS)
    assert "LOCAL-MCP-THREAD-NOTE-MUST-STAY-PRIVATE" not in serialized
    assert "LOCAL-MCP-EVIDENCE-NOTE-MUST-STAY-PRIVATE" not in serialized


def test_read_tools_return_structured_not_found_and_validation_errors(client) -> None:
    project, run, packet = _fixture_packet(client)

    with Session(engine) as db:
        with pytest.raises(McpReadError, match="Research project not found") as missing:
            list_project_runs(db, uuid4())
        assert missing.value.code == "not_found"

        with pytest.raises(McpReadError, match="Research run not found"):
            compare_project_runs(db, project["id"], uuid4())

        with pytest.raises(McpReadError, match="invalid UUID") as invalid:
            get_build_packet(db, "not-a-uuid")
        assert invalid.value.code == "invalid_argument"

        with pytest.raises(McpReadError, match="at most 20"):
            search_opportunities(db, query="pain", limit=21)

        with pytest.raises(McpReadError, match="Build packet not found"):
            verify_build_packet(db, uuid4())

        assert get_opportunity_thread(db, packet["thread_id"])["id"] == packet["thread_id"]
        assert compare_project_runs(db, project["id"], run["id"])["run_id"] == run["id"]


def test_resource_listing_and_resolution_are_safe_and_deterministic(client) -> None:
    project, run, packet = _fixture_packet(client)
    thread_id = packet["thread_id"]
    packet_id = packet["id"]
    delta_uri = f"tasksignal://projects/{project['id']}/runs/{run['id']}/delta"
    thread_uri = f"tasksignal://opportunity-threads/{thread_id}"
    readme_uri = f"tasksignal://build-packets/{packet_id}/artifacts/README.md"
    manifest_uri = f"tasksignal://build-packets/{packet_id}/artifacts/MANIFEST.json"

    with Session(engine) as db:
        templates = list_resource_templates()
        first_listing = list_resources(db)
        second_listing = list_resources(db)
        delta = resolve_resource(db, delta_uri)
        thread = resolve_resource(db, thread_uri)
        readme = resolve_resource(db, readme_uri)
        manifest = resolve_resource(db, manifest_uri)

    assert [template["uri_template"] for template in templates] == [
        "tasksignal://projects/{project_id}/runs/{run_id}/delta",
        "tasksignal://opportunity-threads/{thread_id}",
        "tasksignal://build-packets/{packet_id}/artifacts/{artifact_name}",
    ]
    assert first_listing == second_listing
    uris = {resource["uri"] for resource in first_listing}
    assert {delta_uri, thread_uri, readme_uri, manifest_uri} <= uris
    assert delta["mime_type"] == "application/json"
    assert json.loads(delta["text"])["run_id"] == run["id"]
    assert thread["mime_type"] == "application/json"
    assert not (_all_keys(json.loads(thread["text"])) & FORBIDDEN_KEYS)
    assert readme["mime_type"] == "text/markdown; charset=utf-8"
    assert readme["text"].startswith("# TaskSignal Build Packet")
    assert manifest["mime_type"] == "application/json"
    assert json.loads(manifest["text"])["packet_id"] == packet_id


@pytest.mark.parametrize(
    "uri",
    [
        "https://projects/00000000-0000-0000-0000-000000000000",
        "tasksignal://projects/not-a-uuid/runs/00000000-0000-0000-0000-000000000000/delta",
        "tasksignal://build-packets/00000000-0000-0000-0000-000000000000/artifacts/../README.md",
        "tasksignal://build-packets/00000000-0000-0000-0000-000000000000/artifacts/%2E%2E%2FREADME.md",
        "tasksignal://opportunity-threads/00000000-0000-0000-0000-000000000000?secret=x",
        "tasksignal://opportunity-threads@evil.test/00000000-0000-0000-0000-000000000000",
        " tasksignal://opportunity-threads/00000000-0000-0000-0000-000000000000",
        "tasksignal://opportunity-\nthreads/00000000-0000-0000-0000-000000000000",
        "tasksignal://opportunity-threads/00000000-0000-0000-0000-000000000000\n",
    ],
)
def test_resource_resolver_rejects_malformed_or_unsafe_uris(db_session, uri: str) -> None:
    with pytest.raises(McpReadError) as error:
        resolve_resource(db_session, uri)
    assert error.value.code == "invalid_resource_uri"


def test_resource_resolver_accepts_encoded_enhanced_artifact_name(client) -> None:
    _project, _run, packet = _fixture_packet(client)
    packet_id = UUID(packet["id"])
    enhanced_path = "enhanced/task-pack.md"
    with Session(engine) as db:
        from app.models.all_models import BuildPacket

        row = db.get(BuildPacket, packet_id)
        assert row is not None
        row.generation_mode = "configured_ai"
        row.enhancement_status = "generated"
        row.enhancement_provider = "fixture"
        row.enhancement_model = "fixture-model"
        row.enhancement_template_version = "fixture-v1"
        row.enhanced_artifacts_json = {enhanced_path: "# Safe enhanced task pack\n"}
        db.commit()
        uri = f"tasksignal://build-packets/{packet_id}/artifacts/{quote(enhanced_path, safe='')}"
        listed_uris = {resource["uri"] for resource in list_resources(db)}
        resource = resolve_resource(db, uri)

    assert uri in listed_uris
    assert resource["name"] == enhanced_path
    assert resource["text"] == "# Safe enhanced task pack\n"


def test_thread_and_search_redact_secret_shaped_evidence_values(client) -> None:
    project, _run, packet = _fixture_packet(client)
    thread_id = packet["thread_id"]
    with Session(engine) as db:
        from sqlalchemy import select

        from app.models.all_models import ItemSignal, NormalizedItem, ScanItem

        before = get_opportunity_thread(db, thread_id)
        item_id = UUID(before["current_snapshot"]["evidence_items"][0]["id"])
        item = db.get(NormalizedItem, item_id)
        signal = db.scalar(select(ItemSignal).where(ItemSignal.item_id == item_id))
        assert item is not None
        assert signal is not None
        item.title = "Workflow token=SUPER-SECRET-VALUE"
        item.body = "Contact user@example.test for the private workflow."
        item.url = "https://example.test/item?session_id=SESSION-SECRET"
        signal.evidence_spans_json = [
            "jwt=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signaturevalue"
        ]
        for observation in db.scalars(
            select(ScanItem).where(ScanItem.item_id == item_id)
        ):
            observation.observed_url = item.url
        db.commit()

        thread = get_opportunity_thread(db, thread_id)
        search = search_opportunities(
            db,
            query="manual workflow pain",
            limit=20,
            project_id=project["id"],
        )

    target_thread_item = next(
        row
        for row in thread["current_snapshot"]["evidence_items"]
        if row["id"] == str(item_id)
    )
    target_search_item = next(
        row for row in search["evidence_hits"] if row["id"] == str(item_id)
    )
    serialized = json.dumps([target_thread_item, target_search_item], sort_keys=True)
    for forbidden in (
        "SUPER-SECRET-VALUE",
        "user@example.test",
        "eyJhbGci",
        "SESSION-SECRET",
    ):
        assert forbidden not in serialized
    assert target_thread_item["source_url"] == ""
    assert target_search_item["source_url"] == ""


def test_project_and_run_reads_redact_secret_shaped_metadata(client) -> None:
    project, run, _packet = _fixture_packet(client)
    project_id = UUID(project["id"])
    run_id = UUID(run["id"])
    with Session(engine) as db:
        from app.models.all_models import ResearchProject, ResearchProjectRun

        project_row = db.get(ResearchProject, project_id)
        run_row = db.get(ResearchProjectRun, run_id)
        assert project_row is not None
        assert run_row is not None
        project_row.name = "Project api_key=PROJECT-SECRET-VALUE"
        project_row.description = "password='correct horse battery staple'"
        project_row.query = "refresh_token=PROJECT-REFRESH-SECRET"
        project_row.labels_json = ["client_secret=PROJECT-LABEL-SECRET"]
        run_row.query = "Authorization: token RUN-QUERY-SECRET"
        run_row.source_origin = "https://example.test/?token=RUN-ORIGIN-SECRET"
        db.commit()

        projects = list_projects(db)
        runs = list_project_runs(db, project_id)

    serialized = json.dumps([projects, runs], sort_keys=True)
    for forbidden in (
        "PROJECT-SECRET-VALUE",
        "correct horse battery staple",
        "PROJECT-REFRESH-SECRET",
        "PROJECT-LABEL-SECRET",
        "RUN-QUERY-SECRET",
        "RUN-ORIGIN-SECRET",
    ):
        assert forbidden not in serialized
    assert projects[0]["name"] == "Project [REDACTED]"
    assert projects[0]["labels"] == ["[REDACTED]"]
    assert runs[0]["source_origin"] == ""
