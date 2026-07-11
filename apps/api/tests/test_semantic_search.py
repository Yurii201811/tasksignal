from __future__ import annotations

import json
from uuid import UUID

from app.models.all_models import ItemEmbedding, NormalizedItem
from app.services.ingestion.types import utc_now


def create_fixture_project(client) -> dict:
    response = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Search fixture research",
            "source_type": "fixture",
            "query": "",
            "limit": 100,
            "cadence": "manual",
            "labels": ["search"],
            "enabled": True,
        },
    )
    assert response.status_code == 200, response.text
    project = response.json()
    run = client.post(f"/api/v1/research-projects/{project['id']}/run")
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "completed"
    return project


def test_canonical_search_returns_filtered_redacted_evidence_and_threads(client) -> None:
    project = create_fixture_project(client)
    initial = client.post(
        "/api/v1/search",
        json={
            "query": "github actions workflow failure logs",
            "limit": 20,
            "project_id": project["id"],
        },
    )
    assert initial.status_code == 200, initial.text
    initial_payload = initial.json()
    assert initial_payload["evidence_hits"]
    assert initial_payload["opportunity_threads"]

    selected_thread = initial_payload["opportunity_threads"][0]
    matched_item_id = selected_thread["matched_evidence_ids"][0]
    selected_evidence = next(
        hit for hit in initial_payload["evidence_hits"] if hit["id"] == matched_item_id
    )
    thread_detail = client.get(
        f"/api/v1/opportunity-threads/{selected_thread['id']}"
    ).json()
    decision_note = "LOCAL-THREAD-NOTE-MUST-NOT-SEARCH"
    evidence_note = "LOCAL-EVIDENCE-NOTE-MUST-NOT-SEARCH"
    decision = client.patch(
        f"/api/v1/opportunity-threads/{selected_thread['id']}/decision",
        json={
            "review_state": "promising",
            "review_note": decision_note,
            "expected_version": thread_detail["version"],
        },
    )
    assert decision.status_code == 200, decision.text
    label = client.post(
        "/api/v1/labels",
        json={
            "item_id": matched_item_id,
            "label": "true_signal",
            "user_note": evidence_note,
        },
    )
    assert label.status_code == 200, label.text

    response = client.post(
        "/api/v1/search",
        json={
            "query": "github actions workflow failure logs",
            "limit": 20,
            "project_id": project["id"],
            "source": selected_evidence["source"],
            "signal_type": selected_evidence["signal_type"],
            "review_state": "promising",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["evidence_hits"]
    assert payload["opportunity_threads"]
    assert all(hit["source"] == selected_evidence["source"] for hit in payload["evidence_hits"])
    assert all(
        hit["signal_type"] == selected_evidence["signal_type"]
        for hit in payload["evidence_hits"]
    )
    assert all(thread["project_id"] == project["id"] for thread in payload["opportunity_threads"])
    assert all(thread["review_state"] == "promising" for thread in payload["opportunity_threads"])

    scores_by_item = {hit["id"]: hit["match_score"] for hit in payload["evidence_hits"]}
    for thread in payload["opportunity_threads"]:
        matched_scores = [scores_by_item[item_id] for item_id in thread["matched_evidence_ids"]]
        assert thread["match_score"] == max(matched_scores)
        assert thread["lineage_status"] == "complete"
        assert thread["evidence_readiness"]["level"] in {"weak", "medium", "strong"}
        assert thread["provenance"]["snapshot_id"]
        assert "opportunity_score" not in thread

    evidence_hit = payload["evidence_hits"][0]
    assert evidence_hit["untrusted_evidence"] is True
    assert len(evidence_hit["excerpt"]) <= 240
    assert evidence_hit["provenance"]["evidence_hash"]
    assert evidence_hit["provenance"]["scan_ids"]
    assert evidence_hit["provenance"]["run_ids"]
    assert evidence_hit["provenance"]["project_ids"] == [project["id"]]

    serialized = json.dumps(payload, sort_keys=True)
    assert decision_note not in serialized
    assert evidence_note not in serialized
    for forbidden in (
        "author_hash",
        "raw_json",
        "review_note",
        "user_note",
        "credentials",
        "config_json",
    ):
        assert forbidden not in serialized


def test_search_validates_inputs_and_hides_compatibility_alias_from_openapi(client) -> None:
    project = create_fixture_project(client)
    request = {
        "query": "github actions",
        "limit": 5,
        "project_id": project["id"],
    }

    canonical = client.post("/api/v1/search", json=request)
    compatibility = client.post("/api/search/semantic", json=request)
    blank = client.post("/api/v1/search", json={"query": "   ", "limit": 5})
    too_small = client.post("/api/v1/search", json={"query": "ci", "limit": 0})
    too_large = client.post("/api/v1/search", json={"query": "ci", "limit": 21})
    blank_filter = client.post(
        "/api/v1/search",
        json={"query": "ci", "source": "   "},
    )
    secret_query = "credential-value-must-not-be-echoed"
    private_query = client.post(
        "/api/v1/search",
        json={"query": secret_query, "project_id": project["id"]},
    )

    assert canonical.status_code == 200
    assert compatibility.status_code == 200
    assert canonical.json() == compatibility.json()
    assert blank.status_code == 422
    assert too_small.status_code == 422
    assert too_large.status_code == 422
    assert blank_filter.status_code == 422
    assert private_query.status_code == 200
    assert secret_query not in private_query.text
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/search" in paths
    assert "/api/v1/search/semantic" not in paths
    assert "/api/search" not in paths


def test_search_service_breaks_equal_score_ties_by_evidence_id(db_session) -> None:
    from app.schemas.api import SemanticSearchRequest
    from app.services.search.service import semantic_search

    now = utc_now()
    later_id = UUID("00000000-0000-0000-0000-000000000002")
    earlier_id = UUID("00000000-0000-0000-0000-000000000001")
    for item_id, external_id, text_hash in (
        (later_id, "later", "b" * 64),
        (earlier_id, "earlier", "a" * 64),
    ):
        db_session.add(
            NormalizedItem(
                id=item_id,
                source="fixture",
                external_id=external_id,
                url=f"https://example.test/{external_id}",
                title="Equal semantic evidence",
                body="The same public workflow evidence.",
                author_hash="must-not-be-returned",
                score=1,
                comments_count=0,
                created_at=now,
                fetched_at=now,
                text_hash=text_hash,
                language="en",
                tags=[],
            )
        )
        db_session.add(
            ItemEmbedding(
                item_id=item_id,
                embedding=[1.0, 0.0],
                model_name="tie-model:tie-backend",
            )
        )
    db_session.commit()

    class TieEmbedder:
        model_name = "tie-model"
        backend = "tie-backend"

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            assert texts == ["same"]
            return [[1.0, 0.0]]

    result = semantic_search(
        db_session,
        SemanticSearchRequest(query="same", limit=20),
        embedder=TieEmbedder(),
    )

    assert [hit.id for hit in result.evidence_hits] == [earlier_id, later_id]
    assert [hit.match_score for hit in result.evidence_hits] == [1.0, 1.0]
    assert result.opportunity_threads == []
