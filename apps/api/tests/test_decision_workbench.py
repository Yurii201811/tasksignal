from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.api import routes
from app.db.session import engine
from app.models.all_models import Label


def first_opportunity(client) -> dict:
    client.post("/api/process/demo")
    return client.get("/api/opportunities").json()[0]


def test_opportunity_review_persists_filters_and_survives_regeneration(client) -> None:
    opportunity = first_opportunity(client)
    response = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={
            "review_state": "promising",
            "review_note": "Validate with maintainers.",
        },
    )

    assert response.status_code == 200
    reviewed = response.json()
    assert reviewed["review_state"] == "promising"
    assert reviewed["review_note"] == "Validate with maintainers."
    assert reviewed["decision_updated_at"] is not None
    decision_updated_at = reviewed["decision_updated_at"]
    assert client.get("/api/opportunities?review_state=promising").json()[0]["id"] == (
        opportunity["id"]
    )
    assert client.get("/api/opportunities?review_state=rejected").json() == []

    regenerated = client.post(
        f"/api/opportunities/{opportunity['id']}/regenerate"
    ).json()
    assert regenerated["review_state"] == "promising"
    assert regenerated["review_note"] == "Validate with maintainers."
    assert regenerated["decision_updated_at"] == decision_updated_at

    reset = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "new", "review_note": None},
    ).json()
    assert reset["review_state"] == "new"
    assert reset["review_note"] is None
    assert reset["decision_updated_at"] >= decision_updated_at


def test_opportunity_review_validation_and_missing_record(client) -> None:
    opportunity = first_opportunity(client)
    invalid_state = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "approved", "review_note": None},
    )
    oversized = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "promising", "review_note": "x" * 1001},
    )
    missing = client.patch(
        "/api/opportunities/00000000-0000-0000-0000-000000000000/review",
        json={"review_state": "promising", "review_note": None},
    )

    assert invalid_state.status_code == 422
    assert oversized.status_code == 422
    assert missing.status_code == 404


def test_prompt_enhancement_does_not_change_decision(client, monkeypatch) -> None:
    opportunity = first_opportunity(client)
    reviewed = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "promising", "review_note": "Keep this decision."},
    ).json()
    monkeypatch.setattr(routes.settings, "operator_scan_token", "test-operator-token")
    monkeypatch.setattr(
        routes,
        "enhance_prompt",
        lambda prompt: ("openai", "test-model", f"{prompt}\n\nEnhanced."),
    )

    response = client.post(
        f"/api/opportunities/{opportunity['id']}/enhance?apply=true",
        headers={"X-Operator-Scan-Token": "test-operator-token"},
    )
    refreshed = client.get(f"/api/opportunities/{opportunity['id']}").json()

    assert response.status_code == 200
    assert refreshed["review_state"] == "promising"
    assert refreshed["review_note"] == "Keep this decision."
    assert refreshed["decision_updated_at"] == reviewed["decision_updated_at"]


def test_evidence_reviews_are_append_only_and_legacy_latest_is_unrecognized(client) -> None:
    opportunity = first_opportunity(client)
    item_id = opportunity["evidence_items"][0]["id"]
    first = client.post(
        "/api/labels",
        json={"item_id": item_id, "label": "true_signal", "user_note": "Useful."},
    )
    second = client.post(
        "/api/labels",
        json={"item_id": item_id, "label": "unclear", "user_note": None},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    history = client.get(f"/api/items/{item_id}/labels").json()
    assert [row["label"] for row in history] == ["unclear", "true_signal"]

    with Session(engine) as session:
        session.add(
            Label(
                id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
                item_id=UUID(item_id),
                label="legacy_label",
                user_note="Do not export legacy note.",
                created_at=datetime(2030, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()

    refreshed = client.get(f"/api/opportunities/{opportunity['id']}").json()
    evidence = next(item for item in refreshed["evidence_items"] if item["id"] == item_id)
    assert evidence["review_label"] is None
    assert evidence["review_note"] is None
    assert evidence["review_history_count"] == 3
    evaluation = client.get("/api/evaluation").json()
    assert evaluation["unrecognized_latest_labels"] == 1


def test_decision_context_exports_state_and_readiness_without_local_notes(client) -> None:
    opportunity = first_opportunity(client)
    item_id = opportunity["evidence_items"][0]["id"]
    opportunity_note = "LOCAL-OPPORTUNITY-NOTE-MUST-NOT-EXPORT"
    evidence_note = "LOCAL-EVIDENCE-NOTE-MUST-NOT-EXPORT"
    client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "build_candidate", "review_note": opportunity_note},
    )
    client.post(
        "/api/labels",
        json={
            "item_id": item_id,
            "label": "true_signal",
            "user_note": evidence_note,
        },
    )

    evidence_markdown = client.get(
        f"/api/opportunities/{opportunity['id']}/evidence.md"
    ).text
    task_pack_response = client.get(
        f"/api/opportunities/{opportunity['id']}/task-pack.json"
    )
    task_pack = task_pack_response.json()

    assert task_pack_response.status_code == 200
    assert task_pack["review_state"] == "build_candidate"
    assert task_pack["evidence_readiness"]["level"] in {"weak", "medium", "strong"}
    assert "## Decision Context" in task_pack["markdown"]
    assert "## Decision Context" in evidence_markdown
    serialized = evidence_markdown + task_pack["markdown"] + str(task_pack)
    assert opportunity_note not in serialized
    assert evidence_note not in serialized


def test_label_write_rejects_unknown_missing_and_oversized_inputs(client) -> None:
    opportunity = first_opportunity(client)
    item_id = opportunity["evidence_items"][0]["id"]
    unknown = client.post(
        "/api/labels",
        json={"item_id": item_id, "label": "useful", "user_note": None},
    )
    missing = client.post(
        "/api/labels",
        json={
            "item_id": "00000000-0000-0000-0000-000000000000",
            "label": "true_signal",
            "user_note": None,
        },
    )
    missing_history = client.get(
        "/api/items/00000000-0000-0000-0000-000000000000/labels"
    )
    oversized = client.post(
        "/api/labels",
        json={"item_id": item_id, "label": "true_signal", "user_note": "x" * 501},
    )

    assert unknown.status_code == 422
    assert missing.status_code == 404
    assert missing_history.status_code == 404
    assert oversized.status_code == 422
