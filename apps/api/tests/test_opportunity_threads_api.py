from __future__ import annotations

from app.api import routes
from app.services.ingestion.connectors import BaseConnector
from app.services.ingestion.types import RawFetchedItem, utc_now
from app.workers import scan_pipeline


def evidence(external_id: str, version: str = "v1") -> RawFetchedItem:
    return RawFetchedItem(
        source="threadapi",
        external_id=external_id,
        raw_json={
            "title": f"Painful CI evidence {external_id} {version}",
            "body": (
                "Developers manually copy paste CI failures every week. It takes forever "
                "and teams would pay for a focused workflow dashboard."
            ),
            "created_at": "2026-07-11T00:00:00Z",
            "url": f"https://example.test/evidence/{external_id}",
            "tags": ["ci"],
        },
        fetched_at=utc_now(),
    )


class StaticConnector(BaseConnector):
    name = "threadapi"

    def __init__(self, items: list[RawFetchedItem]) -> None:
        self.items = items

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        return self.items[:limit]


def install_batches(monkeypatch, batches: list[list[RawFetchedItem]]) -> None:
    queue = list(batches)

    def factory() -> BaseConnector:
        return StaticConnector(queue.pop(0))

    monkeypatch.setattr(routes, "PUBLIC_SCAN_API_SOURCES", {"fixture", "threadapi"})
    monkeypatch.setattr(routes.settings, "public_scan_sources", "fixture,threadapi")
    monkeypatch.setitem(scan_pipeline.CONNECTOR_FACTORIES, "threadapi", factory)


def create_project(client) -> dict:
    response = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Thread API research",
            "source_type": "threadapi",
            "query": "ci pain",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def run_project(client, project_id: str) -> dict:
    response = client.post(f"/api/v1/research-projects/{project_id}/run")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    return response.json()


def test_thread_list_detail_decision_history_and_legacy_review_adapter(
    client,
    monkeypatch,
) -> None:
    batch = [evidence("a"), evidence("b")]
    install_batches(monkeypatch, [batch, batch])
    project = create_project(client)
    run_project(client, project["id"])
    run_project(client, project["id"])

    response = client.get(
        f"/api/v1/opportunity-threads?project_id={project['id']}&review_state=new"
    )
    assert response.status_code == 200
    threads = response.json()
    assert len(threads) == 1
    thread = threads[0]
    assert thread["project_id"] == project["id"]
    assert thread["lineage_status"] == "complete"
    assert thread["snapshot_count"] == 2
    assert thread["current_snapshot"]["match_method"] == "exact_evidence"
    assert thread["current_snapshot"]["match_confidence"] == 1.0

    update = client.patch(
        f"/api/v1/opportunity-threads/{thread['id']}/decision",
        json={
            "review_state": "promising",
            "review_note": "Validate with two builders.",
            "expected_version": 1,
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["review_state"] == "promising"
    assert updated["review_note"] == "Validate with two builders."
    assert updated["version"] == 2
    assert updated["decision_history"][-1]["event_type"] == "decision_changed"
    assert updated["decision_history"][-1]["actor_type"] == "human"

    conflict = client.patch(
        f"/api/v1/opportunity-threads/{thread['id']}/decision",
        json={"review_state": "rejected", "expected_version": 1},
    )
    assert conflict.status_code == 409
    no_op = client.patch(
        f"/api/v1/opportunity-threads/{thread['id']}/decision",
        json={
            "review_state": "promising",
            "review_note": "Validate with two builders.",
            "expected_version": 2,
        },
    ).json()
    assert no_op["version"] == 2
    assert len(no_op["decision_history"]) == 1

    snapshot_id = updated["current_snapshot"]["id"]
    legacy = client.patch(
        f"/api/opportunities/{snapshot_id}/review",
        json={"review_state": "build_candidate", "review_note": None},
    )
    assert legacy.status_code == 200
    assert legacy.json()["review_state"] == "build_candidate"
    detail = client.get(f"/api/v1/opportunity-threads/{thread['id']}").json()
    assert detail["review_state"] == "build_candidate"
    assert detail["version"] == 3


def test_human_detach_recovers_future_exact_matching(client, monkeypatch) -> None:
    batch = [evidence("a"), evidence("b")]
    install_batches(monkeypatch, [batch, batch, batch])
    project = create_project(client)
    run_project(client, project["id"])
    run_project(client, project["id"])
    source = client.get(
        f"/api/v1/opportunity-threads?project_id={project['id']}"
    ).json()[0]
    detached_snapshot = source["current_snapshot"]

    response = client.post(
        f"/api/v1/opportunity-threads/{source['id']}/snapshots/"
        f"{detached_snapshot['id']}/detach"
    )

    assert response.status_code == 200, response.text
    detached = response.json()
    assert detached["source_thread"]["snapshot_count"] == 1
    assert detached["new_thread"]["snapshot_count"] == 1
    assert detached["new_thread"]["review_state"] == "new"
    assert detached["new_thread"]["current_snapshot"]["match_method"] == "manual_detach"
    assert (
        detached["new_thread"]["current_snapshot"]["evidence_hash"]
        == detached_snapshot["evidence_hash"]
    )
    assert detached["source_thread"]["decision_history"][-1]["actor_type"] == "human"

    run_project(client, project["id"])
    threads = client.get(
        f"/api/v1/opportunity-threads?project_id={project['id']}"
    ).json()
    by_id = {thread["id"]: thread for thread in threads}
    source_after = by_id[source["id"]]
    corrected_after = by_id[detached["new_thread"]["id"]]
    assert source_after["snapshot_count"] == 1
    assert corrected_after["snapshot_count"] == 2
    assert corrected_after["current_snapshot"]["match_method"] == "exact_evidence"


def test_detach_rejects_unmatched_or_unknown_snapshots(client, monkeypatch) -> None:
    install_batches(monkeypatch, [[evidence("a"), evidence("b")]])
    project = create_project(client)
    run_project(client, project["id"])
    thread = client.get(
        f"/api/v1/opportunity-threads?project_id={project['id']}"
    ).json()[0]

    unmatched = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/snapshots/"
        f"{thread['current_snapshot']['id']}/detach"
    )
    missing = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/snapshots/"
        "00000000-0000-0000-0000-000000000000/detach"
    )

    assert unmatched.status_code == 409
    assert "automatically matched" in unmatched.json()["detail"]
    assert missing.status_code == 404


def test_run_delta_reports_thread_changes_without_unavailable_warning(client, monkeypatch) -> None:
    first = [evidence("a"), evidence("b")]
    second = [evidence("a"), evidence("b")]
    install_batches(monkeypatch, [first, second, []])
    project = create_project(client)
    for _index in range(3):
        run_project(client, project["id"])
    runs = client.get(
        f"/api/v1/research-projects/{project['id']}/runs"
    ).json()
    zero, identical, initial = runs

    first_delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{initial['id']}/delta"
    ).json()
    identical_delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{identical['id']}/delta"
    ).json()
    zero_delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{zero['id']}/delta"
    ).json()

    assert first_delta["opportunity_changes"] == {
        "new": 1,
        "updated": 0,
        "unchanged": 0,
        "not_observed_this_run": 0,
    }
    assert identical_delta["opportunity_changes"] == {
        "new": 0,
        "updated": 0,
        "unchanged": 1,
        "not_observed_this_run": 0,
    }
    assert zero_delta["opportunity_changes"]["not_observed_this_run"] == 1
    assert first_delta["warnings"] == identical_delta["warnings"] == []


def test_thread_delta_tracks_weighted_update_absence_and_return(client, monkeypatch) -> None:
    original = [evidence("a"), evidence("b")]
    updated = [evidence("a", "v2"), evidence("b")]
    install_batches(monkeypatch, [original, updated, [], updated])
    project = create_project(client)
    for _index in range(4):
        run_project(client, project["id"])
    runs = client.get(
        f"/api/v1/research-projects/{project['id']}/runs"
    ).json()
    returned, absent, changed, _initial = runs

    changed_delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{changed['id']}/delta"
    ).json()["opportunity_changes"]
    absent_delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{absent['id']}/delta"
    ).json()["opportunity_changes"]
    returned_delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{returned['id']}/delta"
    ).json()["opportunity_changes"]

    assert changed_delta == {
        "new": 0,
        "updated": 1,
        "unchanged": 0,
        "not_observed_this_run": 0,
    }
    assert absent_delta["not_observed_this_run"] == 1
    assert returned_delta == {
        "new": 0,
        "updated": 0,
        "unchanged": 1,
        "not_observed_this_run": 0,
    }


def test_regenerate_and_enhance_apply_create_new_immutable_snapshots(client, monkeypatch) -> None:
    batch = [evidence("a"), evidence("b")]
    install_batches(monkeypatch, [batch])
    project = create_project(client)
    run_project(client, project["id"])
    thread = client.get(
        f"/api/v1/opportunity-threads?project_id={project['id']}"
    ).json()[0]
    original = thread["current_snapshot"]

    regenerated = client.post(f"/api/v1/opportunities/{original['id']}/regenerate")
    assert regenerated.status_code == 200
    regenerated_snapshot = regenerated.json()
    assert regenerated_snapshot["id"] != original["id"]
    assert regenerated_snapshot["thread_id"] == thread["id"]
    assert regenerated_snapshot["match_method"] == "regenerated"
    original_after = client.get(f"/api/v1/opportunities/{original['id']}").json()
    assert original_after["content_hash"] == original["content_hash"]

    monkeypatch.setattr(routes.settings, "operator_scan_token", "test-token")
    monkeypatch.setattr(
        routes,
        "enhance_prompt",
        lambda prompt: ("openai", "test-model", f"{prompt}\n\nEnhanced."),
    )
    enhancement = client.post(
        f"/api/v1/opportunities/{regenerated_snapshot['id']}/enhance?apply=true",
        headers={"X-Operator-Scan-Token": "test-token"},
    )
    assert enhancement.status_code == 200
    detail = client.get(f"/api/v1/opportunity-threads/{thread['id']}").json()
    assert detail["snapshot_count"] == 3
    assert detail["current_snapshot"]["match_method"] == "enhanced"
    assert detail["current_snapshot"]["generated_prompt"].endswith("Enhanced.")
