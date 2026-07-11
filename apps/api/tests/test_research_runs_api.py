from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.api import routes
from app.db.session import engine
from app.models.all_models import ResearchProject
from app.services.ingestion.connectors import BaseConnector
from app.services.ingestion.types import RawFetchedItem, utc_now
from app.workers import scan_pipeline


def evidence(external_id: str, version: str = "v1") -> RawFetchedItem:
    return RawFetchedItem(
        source="mockapi",
        external_id=external_id,
        raw_json={
            "title": f"Painful CI evidence {external_id} {version}",
            "body": (
                "Developers manually copy paste build failures every week. "
                "It takes forever and teams would pay for a focused workflow."
            ),
            "created_at": "2026-07-11T00:00:00Z",
            "url": f"https://example.test/evidence/{external_id}",
            "tags": ["ci"],
        },
        fetched_at=utc_now(),
    )


class StaticConnector(BaseConnector):
    name = "mockapi"

    def __init__(self, items: list[RawFetchedItem]) -> None:
        self.items = items

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        return self.items[:limit]


class FailingConnector(BaseConnector):
    name = "mockapi"

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        raise RuntimeError("mock forum unavailable")


def install_scan_batches(
    monkeypatch,
    batches: list[list[RawFetchedItem] | Exception],
) -> None:
    queue = list(batches)

    def factory() -> BaseConnector:
        batch = queue.pop(0)
        if isinstance(batch, Exception):
            return FailingConnector()
        return StaticConnector(batch)

    monkeypatch.setattr(routes, "PUBLIC_SCAN_API_SOURCES", {"fixture", "mockapi"})
    monkeypatch.setattr(routes.settings, "public_scan_sources", "fixture,mockapi")
    monkeypatch.setitem(scan_pipeline.CONNECTOR_FACTORIES, "mockapi", factory)


def create_project(client, *, name: str = "CI research") -> dict:
    response = client.post(
        "/api/v1/research-projects",
        json={
            "name": name,
            "description": "Track recurring CI workflow pain.",
            "source_type": "mockapi",
            "query": "ci pain",
            "limit": 20,
            "cadence": "manual",
            "labels": ["ci"],
            "enabled": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def run_project(client, project_id: str) -> dict:
    response = client.post(f"/api/v1/research-projects/{project_id}/run")
    assert response.status_code == 200
    return response.json()


def test_v1_is_canonical_and_v1x_compatibility_alias_is_hidden_from_openapi(
    client,
    monkeypatch,
) -> None:
    install_scan_batches(monkeypatch, [])
    project = create_project(client)

    canonical = client.get("/api/v1/research-projects")
    compatibility = client.get("/api/research-projects")

    assert canonical.status_code == 200
    assert canonical.json() == compatibility.json() == [project]
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/research-projects" in paths
    assert "/api/research-projects" not in paths


def test_process_stage_advertises_canonical_demo_endpoint_and_keeps_alias(client) -> None:
    canonical = client.post("/api/v1/process/detect")
    compatibility = client.post("/api/process/detect")

    expected = {
        "status": "available in the combined demo pipeline",
        "endpoint": "/api/v1/process/demo",
    }
    assert canonical.status_code == compatibility.status_code == 200
    assert canonical.json() == compatibility.json() == expected


def test_patch_updates_only_supplied_fields_and_preserves_run_snapshots(
    client,
    monkeypatch,
) -> None:
    install_scan_batches(monkeypatch, [[evidence("a")], [evidence("b")]])
    project = create_project(client)
    run_project(client, project["id"])

    patch_response = client.patch(
        f"/api/v1/research-projects/{project['id']}",
        json={
            "name": "Updated CI research",
            "description": None,
            "query": "updated query",
            "limit": 7,
            "labels": ["updated", "  ci  "],
        },
    )

    assert patch_response.status_code == 200
    updated = patch_response.json()
    assert updated["name"] == "Updated CI research"
    assert updated["description"] is None
    assert updated["source_type"] == "mockapi"
    assert updated["query"] == "updated query"
    assert updated["limit"] == 7
    assert updated["labels"] == ["updated", "ci"]
    run_project(client, project["id"])

    history = client.get(
        f"/api/v1/research-projects/{project['id']}/runs"
    ).json()
    assert [entry["sequence"] for entry in history] == [2, 1]
    assert history[1]["query"] == "ci pain"
    assert history[1]["requested_limit"] == 20
    assert history[0]["query"] == "updated query"
    assert history[0]["requested_limit"] == 7


def test_patch_rejects_null_required_fields_and_invalid_sources(client, monkeypatch) -> None:
    install_scan_batches(monkeypatch, [])
    project = create_project(client)

    null_name = client.patch(
        f"/api/v1/research-projects/{project['id']}",
        json={"name": None},
    )
    invalid_source = client.patch(
        f"/api/v1/research-projects/{project['id']}",
        json={"source_type": "private-forum"},
    )

    assert null_name.status_code == 422
    assert invalid_source.status_code == 400
    saved = client.get(f"/api/v1/research-projects/{project['id']}").json()
    assert saved["name"] == "CI research"
    assert saved["source_type"] == "mockapi"


def test_run_delta_reports_first_and_identical_runs_precisely(client, monkeypatch) -> None:
    batch = [evidence("a"), evidence("b")]
    install_scan_batches(monkeypatch, [batch, batch])
    project = create_project(client)
    run_project(client, project["id"])
    run_project(client, project["id"])
    history = client.get(
        f"/api/v1/research-projects/{project['id']}/runs"
    ).json()
    second, first = history

    first_delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{first['id']}/delta"
    )
    identical_delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{second['id']}/delta"
    )

    assert first_delta.status_code == 200
    assert first_delta.json()["evidence_changes"] == {
        "new": 2,
        "seen_before": 0,
        "updated": 0,
        "unchanged": 0,
        "not_observed_this_run": 0,
    }
    payload = identical_delta.json()
    assert payload["previous_run_id"] == first["id"]
    assert payload["evidence_changes"] == {
        "new": 0,
        "seen_before": 2,
        "updated": 0,
        "unchanged": 2,
        "not_observed_this_run": 0,
    }
    assert payload["signal_changes"] == payload["evidence_changes"]
    assert payload["opportunity_changes"] == {
        "new": 0,
        "updated": 0,
        "unchanged": 1,
        "not_observed_this_run": 0,
    }
    assert payload["warnings"] == []
    assert "deleted" not in identical_delta.text
    assert "resolved" not in identical_delta.text


def test_first_project_run_reports_evidence_seen_by_an_earlier_manual_scan(
    client,
    monkeypatch,
) -> None:
    batch = [evidence("already-known")]
    install_scan_batches(monkeypatch, [batch, batch])
    manual = client.post(
        "/api/v1/scans",
        json={"source": "mockapi", "query": "ci pain", "limit": 20},
    )
    assert manual.status_code == 200
    project = create_project(client)
    run_project(client, project["id"])
    run = client.get(
        f"/api/v1/research-projects/{project['id']}/runs"
    ).json()[0]

    delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{run['id']}/delta"
    ).json()

    assert delta["evidence_changes"]["new"] == 0
    assert delta["evidence_changes"]["seen_before"] == 1
    assert delta["signal_changes"]["new"] == 0
    assert delta["signal_changes"]["seen_before"] == 1


def test_run_delta_distinguishes_new_returning_updated_unchanged_and_absent(
    client,
    monkeypatch,
) -> None:
    run_one = [evidence("a"), evidence("b"), evidence("returning")]
    run_two = [evidence("a"), evidence("b"), evidence("not-observed")]
    run_three = [
        evidence("a", "v2"),
        evidence("b"),
        evidence("returning"),
        evidence("brand-new"),
    ]
    install_scan_batches(monkeypatch, [run_one, run_two, run_three])
    project = create_project(client)
    for _index in range(3):
        run_project(client, project["id"])
    target = client.get(
        f"/api/v1/research-projects/{project['id']}/runs"
    ).json()[0]

    response = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{target['id']}/delta"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_changes"] == {
        "new": 2,
        "seen_before": 2,
        "updated": 1,
        "unchanged": 1,
        "not_observed_this_run": 1,
    }
    assert payload["signal_changes"] == payload["evidence_changes"]
    assert payload["generated_snapshots"]["clusters"] >= 1
    assert payload["generated_snapshots"]["opportunities"] >= 1


def test_zero_failed_and_cross_project_run_delta_boundaries(client, monkeypatch) -> None:
    install_scan_batches(
        monkeypatch,
        [[evidence("prior")], [], RuntimeError("source unavailable")],
    )
    first_project = create_project(client, name="First")
    first_scan = run_project(client, first_project["id"])
    assert first_scan["status"] == "completed"
    run_project(client, first_project["id"])
    failed_scan = run_project(client, first_project["id"])
    assert failed_scan["status"] == "failed"
    history = client.get(
        f"/api/v1/research-projects/{first_project['id']}/runs"
    ).json()
    failed, zero, first = history
    assert failed["lineage_status"] == "incomplete"

    zero_delta = client.get(
        f"/api/v1/research-projects/{first_project['id']}/runs/{zero['id']}/delta"
    )
    failed_delta = client.get(
        f"/api/v1/research-projects/{first_project['id']}/runs/{failed['id']}/delta"
    )
    assert zero_delta.status_code == 200
    assert zero_delta.json()["evidence_changes"]["not_observed_this_run"] == 1
    assert failed_delta.status_code == 409

    install_scan_batches(monkeypatch, [])
    second_project = create_project(client, name="Second")
    cross_project = client.get(
        f"/api/v1/research-projects/{second_project['id']}/runs/{first['id']}/delta"
    )
    assert cross_project.status_code == 404


def test_legacy_last_scan_is_exposed_as_untracked_without_inferred_lineage(
    client,
    monkeypatch,
) -> None:
    install_scan_batches(monkeypatch, [[evidence("legacy")]])
    project = create_project(client)
    manual_scan = client.post(
        "/api/v1/scans",
        json={"source": "mockapi", "query": "legacy", "limit": 5},
    ).json()
    with Session(engine) as session:
        stored = session.get(ResearchProject, UUID(project["id"]))
        assert stored is not None
        stored.last_scan_id = UUID(manual_scan["id"])
        stored.run_count = 1
        session.commit()

    history = client.get(
        f"/api/v1/research-projects/{project['id']}/runs"
    ).json()

    assert len(history) == 1
    assert history[0]["id"] == manual_scan["id"]
    assert history[0]["sequence"] is None
    assert history[0]["requested_limit"] is None
    assert history[0]["lineage_status"] == "untracked"
    delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{manual_scan['id']}/delta"
    )
    assert delta.status_code == 409
    assert "untracked" in delta.json()["detail"].lower()


def test_concurrent_project_routes_keep_run_count_and_latest_scan_consistent(
    client,
    monkeypatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(routes, "PUBLIC_SCAN_API_SOURCES", {"fixture", "mockapi"})
    monkeypatch.setattr(routes.settings, "public_scan_sources", "fixture,mockapi")
    monkeypatch.setitem(
        scan_pipeline.CONNECTOR_FACTORIES,
        "mockapi",
        lambda: StaticConnector([evidence("concurrent")]),
    )
    project = create_project(client)

    def run_once(_index: int) -> dict:
        return client.post(
            f"/api/v1/research-projects/{project['id']}/run"
        ).json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        scans = list(executor.map(run_once, range(2)))

    assert [scan["status"] for scan in scans] == ["completed", "completed"]
    saved = client.get(f"/api/v1/research-projects/{project['id']}").json()
    history = client.get(
        f"/api/v1/research-projects/{project['id']}/runs"
    ).json()
    assert saved["run_count"] == 2
    assert [entry["sequence"] for entry in history] == [2, 1]
    assert saved["last_scan_id"] == history[0]["scan_id"]
