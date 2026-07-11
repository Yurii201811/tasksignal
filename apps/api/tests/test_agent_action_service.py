from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.services.agent_actions.service import (
    IDEMPOTENCY_CONFLICT,
    IDEMPOTENCY_IN_PROGRESS,
    IDEMPOTENCY_REPLAY,
    InvalidActionTransition,
    InvalidIdempotencyKey,
    UnsupportedAgentAction,
    canonical_request_hash,
    complete_agent_action,
    fail_agent_action,
    hash_idempotency_key,
    redacted_agent_action,
    summarize_request,
    summarize_result,
)
from app.services.agent_actions.service import (
    _reserve_agent_action as reserve_agent_action,
)

NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
SESSION_ID = uuid4()
THREAD_ID = uuid4()


def test_request_hash_is_canonical_namespaced_and_covers_private_values() -> None:
    first = {
        "thread_id": THREAD_ID,
        "expected_version": 7,
        "review_state": "build_candidate",
        "note": "private note one",
        "nested": {"second": 2, "first": 1},
    }
    reordered = {
        "nested": {"first": 1, "second": 2},
        "note": "private note one",
        "review_state": "build_candidate",
        "expected_version": 7,
        "thread_id": str(THREAD_ID),
    }

    digest = canonical_request_hash(
        "set_opportunity_decision",
        first,
        capability="set_opportunity_decision",
    )

    assert digest == canonical_request_hash(
        "set_opportunity_decision",
        reordered,
        capability="set_opportunity_decision",
    )
    assert len(digest) == 64
    assert digest == digest.lower()
    assert "private note one" not in digest
    assert digest != canonical_request_hash(
        "set_opportunity_decision",
        {**reordered, "note": "private note two"},
        capability="set_opportunity_decision",
    )
    assert digest != canonical_request_hash(
        "create_build_packet",
        reordered,
        capability="create_build_packet",
    )


def test_idempotency_hash_is_bound_to_session_and_rejects_unsafe_keys() -> None:
    raw_key = "create-packet-2026-07-11-0001"
    digest = hash_idempotency_key(SESSION_ID, raw_key)

    assert digest == hash_idempotency_key(SESSION_ID, raw_key)
    assert digest != hash_idempotency_key(uuid4(), raw_key)
    assert raw_key not in digest
    assert len(digest) == 64

    for invalid in ("", "short", " leading-space", "trailing-space ", "x" * 257):
        with pytest.raises(InvalidIdempotencyKey) as error:
            hash_idempotency_key(SESSION_ID, invalid)
        assert error.value.code == "invalid_idempotency_key"
        if invalid:
            assert invalid not in str(error.value)


def test_request_summary_is_tool_specific_bounded_and_excludes_private_fields() -> None:
    request = {
        "thread_id": THREAD_ID,
        "expected_version": 4,
        "review_state": "build_candidate",
        "note": "local decision note",
        "query": "private query",
        "evidence": "raw evidence text",
        "url": "https://user:secret@example.test/private?token=secret",
        "session_secret": "raw-session-secret",
        "idempotency_key": "raw-key",
        "unknown": "x" * 20_000,
    }

    summary = summarize_request("set_opportunity_decision", request)

    assert summary == {
        "expected_version": 4,
        "review_state": "build_candidate",
        "thread_id": str(THREAD_ID),
    }
    encoded = json.dumps(summary, sort_keys=True)
    for forbidden in (
        "local decision note",
        "private query",
        "raw evidence text",
        "https://",
        "secret",
        "raw-key",
    ):
        assert forbidden not in encoded
    assert len(encoded.encode()) <= 2_048


def test_result_summary_keeps_only_replay_safe_contract_fields() -> None:
    packet_id = uuid4()
    result = {
        "id": packet_id,
        "thread_id": THREAD_ID,
        "generation_mode": "deterministic",
        "enhancement_status": "not_requested",
        "artifact_count": 10,
        "manifest": {"query": "private", "url": "https://private.test"},
        "review_note": "never persist me",
        "download_url": "https://private.test/packet.zip?token=secret",
    }

    summary = summarize_result("create_build_packet", result)

    assert summary == {
        "artifact_count": 10,
        "enhancement_status": "not_requested",
        "generation_mode": "deterministic",
        "id": str(packet_id),
        "thread_id": str(THREAD_ID),
    }
    encoded = json.dumps(summary, sort_keys=True)
    assert "private" not in encoded
    assert "url" not in encoded
    assert "secret" not in encoded


def test_unknown_tool_or_capability_is_rejected_without_echoing_attacker_input(
    db_session,
) -> None:
    session = _persist_agent_session(db_session)
    unsafe_values = (
        ("https://private.test/?token=secret", "create_project"),
        ("create_project", "query_with_private_terms"),
    )

    for tool_name, capability in unsafe_values:
        with pytest.raises(UnsupportedAgentAction) as error:
            reserve_agent_action(
                db_session,
                session_id=session.id,
                capability=capability,
                tool_name=tool_name,
                idempotency_key="unknown-action-2026-07-11",
                request={},
                now=NOW,
            )
        assert error.value.code == "unsupported_agent_action"
        assert "private" not in str(error.value)
        assert "query" not in str(error.value)


def test_public_audit_projection_reapplies_allowlists_and_hides_internal_hashes(
    db_session,
) -> None:
    session = _persist_agent_session(db_session)
    claim = reserve_agent_action(
        db_session,
        session_id=session.id,
        capability="create_build_packet",
        tool_name="create_build_packet",
        idempotency_key="packet-audit-2026-07-11",
        request={"thread_id": THREAD_ID, "expected_version": 3},
        now=NOW,
    )
    claim.event.request_summary_json = {
        **claim.event.request_summary_json,
        "query": "private query injected before completion",
        "url": "https://private.test/?token=secret",
    }
    event = complete_agent_action(
        db_session,
        claim=claim,
        result={"id": uuid4(), "thread_id": THREAD_ID, "artifact_count": 10},
        now=NOW,
    )
    assert event.request_summary_json == {
        "expected_version": 3,
        "thread_id": str(THREAD_ID),
    }
    db_session.expire_all()
    reserved = _operation_events(db_session, claim.operation_id)[0]
    assert reserved.request_summary_json == {
        "expected_version": 3,
        "thread_id": str(THREAD_ID),
    }
    # A compromised/legacy row must not turn the audit response into a pass-through.
    event.request_summary_json = {
        **event.request_summary_json,
        "query": "private query",
        "url": "https://private.test/?token=secret",
    }
    event.result_summary_json = {
        **event.result_summary_json,
        "message": "private traceback",
    }

    projection = redacted_agent_action(event)
    serialized = json.dumps(projection, sort_keys=True, default=str)

    assert projection["event_status"] == "succeeded"
    assert projection["request_summary"] == {
        "expected_version": 3,
        "thread_id": str(THREAD_ID),
    }
    assert "idempotency_key_hash" not in projection
    assert "request_hash" not in projection
    assert "private" not in serialized
    assert "https://" not in serialized


def test_reserved_success_and_replay_are_append_only_and_replay_safe(db_session) -> None:
    session = _persist_agent_session(db_session)
    raw_key = "decision-2026-07-11-0001"
    request = {
        "thread_id": THREAD_ID,
        "expected_version": 3,
        "review_state": "build_candidate",
        "note": "private note must only influence the request hash",
    }

    claim = reserve_agent_action(
        db_session,
        session_id=session.id,
        capability="set_opportunity_decision",
        tool_name="set_opportunity_decision",
        idempotency_key=raw_key,
        request=request,
        now=NOW,
    )
    success = complete_agent_action(
        db_session,
        claim=claim,
        result={
            "thread_id": THREAD_ID,
            "version": 4,
            "review_state": "build_candidate",
            "review_note": "private note must not be audited",
        },
        now=NOW,
    )
    replay = reserve_agent_action(
        db_session,
        session_id=session.id,
        capability="set_opportunity_decision",
        tool_name="set_opportunity_decision",
        idempotency_key=raw_key,
        request=request,
        now=NOW,
    )
    db_session.flush()

    events = _operation_events(db_session, claim.operation_id)
    assert claim.outcome == "reserved"
    assert replay.outcome == "replay"
    assert replay.error_code == IDEMPOTENCY_REPLAY
    assert replay.replay_result == success.result_summary_json
    assert [event.event_status for event in events] == [
        "reserved",
        "succeeded",
        "replayed",
    ]
    assert len({event.operation_id for event in events}) == 1
    assert events[0].id != events[1].id != events[2].id
    assert events[0].idempotency_key_hash == hash_idempotency_key(session.id, raw_key)

    serialized = json.dumps(
        [
            {
                "request": event.request_summary_json,
                "result": event.result_summary_json,
                "key_hash": event.idempotency_key_hash,
            }
            for event in events
        ],
        sort_keys=True,
    )
    for forbidden in (raw_key, "private note", "review_note"):
        assert forbidden not in serialized


def test_duplicate_in_flight_and_conflicting_reuse_append_stable_audit_events(
    db_session,
) -> None:
    session = _persist_agent_session(db_session)
    raw_key = "project-update-2026-07-11-0001"
    request = {
        "project_id": uuid4(),
        "expected_version": 2,
        "enabled": True,
        "query": "private query one",
    }

    reserved = reserve_agent_action(
        db_session,
        session_id=session.id,
        capability="update_project",
        tool_name="update_project",
        idempotency_key=raw_key,
        request=request,
        now=NOW,
    )
    in_progress = reserve_agent_action(
        db_session,
        session_id=session.id,
        capability="update_project",
        tool_name="update_project",
        idempotency_key=raw_key,
        request=request,
        now=NOW,
    )
    conflict = reserve_agent_action(
        db_session,
        session_id=session.id,
        capability="update_project",
        tool_name="update_project",
        idempotency_key=raw_key,
        request={**request, "query": "private query two"},
        now=NOW,
    )

    events = _operation_events(db_session, reserved.operation_id)
    assert in_progress.outcome == "in_progress"
    assert in_progress.error_code == IDEMPOTENCY_IN_PROGRESS
    assert conflict.outcome == "conflict"
    assert conflict.error_code == IDEMPOTENCY_CONFLICT
    assert [event.event_status for event in events] == [
        "reserved",
        "replayed",
        "conflict",
    ]
    assert events[1].error_code == IDEMPOTENCY_IN_PROGRESS
    assert events[2].error_code == IDEMPOTENCY_CONFLICT


def test_failure_is_append_only_redacted_and_terminal_transition_cannot_repeat(
    db_session,
) -> None:
    session = _persist_agent_session(db_session)
    claim = reserve_agent_action(
        db_session,
        session_id=session.id,
        capability="create_build_packet",
        tool_name="create_build_packet",
        idempotency_key="packet-2026-07-11-0001",
        request={
            "thread_id": THREAD_ID,
            "expected_version": 8,
            "use_configured_ai": False,
        },
        now=NOW,
    )

    failure = fail_agent_action(
        db_session,
        claim=claim,
        error_code="version_conflict",
        result={
            "thread_id": THREAD_ID,
            "expected_version": 8,
            "current_version": 9,
            "message": "secret traceback at https://private.test/?token=secret",
        },
        now=NOW,
    )

    assert failure.event_status == "failed"
    assert failure.error_code == "version_conflict"
    assert failure.result_summary_json == {
        "current_version": 9,
        "expected_version": 8,
        "thread_id": str(THREAD_ID),
    }
    with pytest.raises(InvalidActionTransition) as error:
        complete_agent_action(db_session, claim=claim, result={}, now=NOW)
    assert error.value.code == "invalid_action_transition"
    assert [event.event_status for event in _operation_events(db_session, claim.operation_id)] == [
        "reserved",
        "failed",
    ]


def _persist_agent_session(db_session):
    from app.models.all_models import AgentSession

    session = AgentSession(
        client_name="Codex",
        client_version="1.0",
        process_instance_id=uuid4(),
        transport="stdio",
        secret_hash="a" * 64,
        requested_capabilities_json=["set_opportunity_decision"],
        approved_capabilities_json=["set_opportunity_decision"],
        status="approved",
        approval_source="ui",
        approved_at=NOW,
        last_heartbeat_at=NOW,
        expires_at=NOW + timedelta(seconds=60),
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(session)
    db_session.flush()
    return session


def _operation_events(db_session, operation_id):
    from sqlalchemy import select

    from app.models.all_models import AgentAction

    return list(
        db_session.scalars(
            select(AgentAction)
            .where(AgentAction.operation_id == operation_id)
            .order_by(AgentAction.event_sequence)
        )
    )
