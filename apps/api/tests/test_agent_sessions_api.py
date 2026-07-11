from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.api import routes
from app.db.session import engine
from app.services.agent_actions.service import (
    _reserve_agent_action as reserve_agent_action,
)
from app.services.agent_actions.service import (
    complete_agent_action,
)
from app.services.agent_sessions import (
    CONFIGURED_AI_CAPABILITY,
    STANDARD_WRITE_CAPABILITIES,
    hash_session_secret,
)

RAW_SECRET = "agent-process-secret-with-more-than-thirty-two-bytes"
OPERATOR_TOKEN = "agent-session-operator-token"
OPERATOR_HEADERS = {"X-Operator-Scan-Token": OPERATOR_TOKEN}


@pytest.fixture(autouse=True)
def configure_operator_token(monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "operator_scan_token", OPERATOR_TOKEN)


def registration_payload(*, include_ai: bool = False) -> dict:
    capabilities = set(STANDARD_WRITE_CAPABILITIES)
    if include_ai:
        capabilities.add(CONFIGURED_AI_CAPABILITY)
    return {
        "client_name": "TaskSignal MCP",
        "client_version": "1.0.0a1",
        "process_instance_id": str(uuid4()),
        "transport": "stdio",
        "secret_hash": hash_session_secret(RAW_SECRET),
        "requested_capabilities": sorted(capabilities),
    }


def test_session_registration_approval_heartbeat_revoke_and_redaction(client) -> None:
    payload = registration_payload(include_ai=True)
    registered = client.post("/api/v1/agent-sessions", json=payload)
    assert registered.status_code == 201, registered.text
    session = registered.json()
    assert session["status"] == "pending"
    assert session["effective_status"] == "pending"
    assert session["version"] == 1
    assert session["requested_capabilities"] == payload["requested_capabilities"]
    assert "secret" not in registered.text.lower()
    assert RAW_SECRET not in registered.text
    session_id = session["id"]

    listed = client.get("/api/v1/agent-sessions", headers=OPERATOR_HEADERS)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [session_id]
    assert "secret" not in listed.text.lower()

    wrong_secret = client.post(
        f"/api/v1/agent-sessions/{session_id}/heartbeat",
        json={"expected_version": 1},
        headers={"Authorization": "Bearer wrong-secret"},
    )
    assert wrong_secret.status_code == 401
    assert "not found" not in wrong_secret.text.lower()

    heartbeat = client.post(
        f"/api/v1/agent-sessions/{session_id}/heartbeat",
        json={"expected_version": 1},
        headers={"Authorization": f"Bearer {RAW_SECRET}"},
    )
    assert heartbeat.status_code == 200, heartbeat.text
    assert heartbeat.json()["status"] == "pending"
    assert heartbeat.json()["version"] == 2

    stale = client.post(
        f"/api/v1/agent-sessions/{session_id}/approve",
        json={"expected_version": 1, "use_configured_ai": False},
        headers=OPERATOR_HEADERS,
    )
    assert stale.status_code == 409

    approved = client.post(
        f"/api/v1/agent-sessions/{session_id}/approve",
        json={"expected_version": 2, "use_configured_ai": False},
        headers=OPERATOR_HEADERS,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["version"] == 3
    assert set(approved.json()["approved_capabilities"]) == STANDARD_WRITE_CAPABILITIES
    assert CONFIGURED_AI_CAPABILITY not in approved.json()["approved_capabilities"]

    renewed = client.post(
        f"/api/v1/agent-sessions/{session_id}/heartbeat",
        json={"expected_version": 3},
        headers={"Authorization": f"Bearer {RAW_SECRET}"},
    )
    assert renewed.status_code == 200
    assert renewed.json()["version"] == 4

    revoked = client.post(
        f"/api/v1/agent-sessions/{session_id}/revoke",
        json={"expected_version": 4},
        headers=OPERATOR_HEADERS,
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert revoked.json()["version"] == 5
    denied_after_revoke = client.post(
        f"/api/v1/agent-sessions/{session_id}/heartbeat",
        json={"expected_version": 5},
        headers={"Authorization": f"Bearer {RAW_SECRET}"},
    )
    assert denied_after_revoke.status_code == 409
    assert client.get(
        f"/api/v1/agent-sessions/{session_id}/actions",
        headers=OPERATOR_HEADERS,
    ).json() == []


def test_operator_controls_cannot_be_self_approved_or_read_by_agent(client) -> None:
    registered = client.post(
        "/api/v1/agent-sessions",
        json=registration_payload(include_ai=True),
    ).json()
    session_id = registered["id"]

    for response in (
        client.get("/api/v1/agent-sessions"),
        client.get(f"/api/v1/agent-sessions/{session_id}"),
        client.get(f"/api/v1/agent-sessions/{session_id}/actions"),
        client.post(
            f"/api/v1/agent-sessions/{session_id}/approve",
            json={"expected_version": 1, "use_configured_ai": True},
        ),
        client.post(
            f"/api/v1/agent-sessions/{session_id}/revoke",
            json={"expected_version": 1},
        ),
    ):
        assert response.status_code == 403

    forged_tty = client.post(
        f"/api/v1/agent-sessions/{session_id}/approve",
        json={
            "expected_version": 1,
            "use_configured_ai": True,
            "approval_source": "interactive_tty",
        },
        headers=OPERATOR_HEADERS,
    )
    assert forged_tty.status_code == 422
    approved = client.post(
        f"/api/v1/agent-sessions/{session_id}/approve",
        json={"expected_version": 1, "use_configured_ai": True},
        headers=OPERATOR_HEADERS,
    )
    assert approved.status_code == 200
    assert approved.json()["approval_source"] == "ui"


def test_listing_materializes_every_expired_session(client) -> None:
    session_ids = []
    for index in range(2):
        payload = registration_payload()
        payload["client_name"] = f"Expired process {index}"
        payload["secret_hash"] = hash_session_secret(
            f"expired-agent-process-secret-{index}-with-enough-entropy"
        )
        response = client.post("/api/v1/agent-sessions", json=payload)
        assert response.status_code == 201
        session_ids.append(UUID(response.json()["id"]))

    expired_heartbeat = datetime.now(UTC) - timedelta(minutes=2)
    with Session(engine) as db:
        from app.models.all_models import AgentSession

        for session_id in session_ids:
            row = db.get(AgentSession, session_id)
            assert row is not None
            row.last_heartbeat_at = expired_heartbeat
            row.expires_at = expired_heartbeat + timedelta(seconds=60)
        db.commit()

    listed = client.get("/api/v1/agent-sessions", headers=OPERATOR_HEADERS)
    assert listed.status_code == 200
    assert {row["status"] for row in listed.json()} == {"expired"}
    with Session(engine) as db:
        from app.models.all_models import AgentSession

        assert {db.get(AgentSession, session_id).status for session_id in session_ids} == {
            "expired"
        }


def test_ai_approval_is_separate_and_clean_exit_is_terminal(client) -> None:
    payload = registration_payload(include_ai=True)
    first = client.post("/api/v1/agent-sessions", json=payload)
    assert first.status_code == 201
    session_id = first.json()["id"]
    approved = client.post(
        f"/api/v1/agent-sessions/{session_id}/approve",
        json={"expected_version": 1, "use_configured_ai": True},
        headers=OPERATOR_HEADERS,
    )
    assert approved.status_code == 200
    assert CONFIGURED_AI_CAPABILITY in approved.json()["approved_capabilities"]

    exited = client.post(
        f"/api/v1/agent-sessions/{session_id}/exit",
        json={"expected_version": 2},
        headers={"Authorization": f"Bearer {RAW_SECRET}"},
    )
    assert exited.status_code == 200
    assert exited.json()["status"] == "exited"
    assert exited.json()["effective_status"] == "exited"
    assert client.post(
        f"/api/v1/agent-sessions/{session_id}/heartbeat",
        json={"expected_version": 3},
        headers={"Authorization": f"Bearer {RAW_SECRET}"},
    ).status_code == 409


def test_session_registration_rejects_duplicate_process_or_secret_hash(client) -> None:
    payload = registration_payload()
    assert client.post("/api/v1/agent-sessions", json=payload).status_code == 201
    duplicate = client.post("/api/v1/agent-sessions", json=payload)
    assert duplicate.status_code == 409
    assert RAW_SECRET not in duplicate.text
    assert payload["secret_hash"] not in duplicate.text


def test_session_action_audit_endpoint_is_append_only_and_redacted(client) -> None:
    payload = registration_payload()
    registered = client.post("/api/v1/agent-sessions", json=payload).json()
    session_id = UUID(registered["id"])
    thread_id = uuid4()
    raw_key = "decision-audit-2026-07-11-0001"
    private_note = "PRIVATE-DECISION-NOTE-MUST-NOT-AUDIT"
    with Session(engine) as db:
        claim = reserve_agent_action(
            db,
            session_id=session_id,
            capability="set_opportunity_decision",
            tool_name="set_opportunity_decision",
            idempotency_key=raw_key,
            request={
                "thread_id": thread_id,
                "expected_version": 4,
                "review_state": "build_candidate",
                "review_note": private_note,
                "url": "https://private.test/?token=secret",
            },
        )
        complete_agent_action(
            db,
            claim=claim,
            result={
                "thread_id": thread_id,
                "version": 5,
                "review_state": "build_candidate",
                "review_note": private_note,
            },
        )
        db.commit()

    response = client.get(
        f"/api/v1/agent-sessions/{session_id}/actions",
        headers=OPERATOR_HEADERS,
    )
    assert response.status_code == 200
    actions = response.json()
    assert [row["event_status"] for row in actions] == ["succeeded", "reserved"]
    serialized = response.text
    for forbidden in (
        raw_key,
        private_note,
        "idempotency_key_hash",
        "request_hash",
        "https://",
        "token",
    ):
        assert forbidden not in serialized


def test_human_revoke_wins_a_concurrent_heartbeat(client) -> None:
    registered = client.post(
        "/api/v1/agent-sessions",
        json=registration_payload(),
    ).json()
    session_id = registered["id"]
    approved = client.post(
        f"/api/v1/agent-sessions/{session_id}/approve",
        json={"expected_version": 1, "use_configured_ai": False},
        headers=OPERATOR_HEADERS,
    ).json()
    barrier = Barrier(2)

    def heartbeat():
        barrier.wait()
        return client.post(
            f"/api/v1/agent-sessions/{session_id}/heartbeat",
            json={"expected_version": approved["version"]},
            headers={"Authorization": f"Bearer {RAW_SECRET}"},
        )

    def revoke():
        barrier.wait()
        return client.post(
            f"/api/v1/agent-sessions/{session_id}/revoke",
            json={"expected_version": approved["version"]},
            headers=OPERATOR_HEADERS,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        heartbeat_response = executor.submit(heartbeat)
        revoke_response = executor.submit(revoke)
        responses = [heartbeat_response.result(), revoke_response.result()]

    assert responses[1].status_code == 200
    assert responses[0].status_code in {200, 409}
    saved = client.get(
        f"/api/v1/agent-sessions/{session_id}",
        headers=OPERATOR_HEADERS,
    ).json()
    assert saved["status"] == "revoked"
    assert saved["effective_status"] == "revoked"
