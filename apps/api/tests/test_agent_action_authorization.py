from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.all_models import AgentAction, AgentSession
from app.services.agent_actions.service import (
    CREATE_PROJECT_EXPECTED_VERSION,
    InvalidAgentRequest,
    InvalidExpectedVersion,
    ReservedAgentActionDenied,
)
from app.services.agent_actions.service import (
    _authorize_and_reserve_agent_action as authorize_and_reserve_agent_action,
)
from app.services.agent_sessions import (
    CONFIGURED_AI_CAPABILITY,
    STANDARD_WRITE_CAPABILITIES,
    SessionAuthenticationError,
    SessionCapabilityError,
    SessionStateError,
    hash_session_secret,
)

NOW = datetime(2026, 7, 11, 14, 0, tzinfo=UTC)
RAW_SECRET = "agent-action-gateway-secret-with-at-least-32-bytes"


def test_gateway_authenticates_live_approved_session_and_derives_capability(db_session) -> None:
    session = _persist_session(db_session)
    project_id = uuid4()

    claim = authorize_and_reserve_agent_action(
        db_session,
        session_id=session.id,
        raw_session_secret=RAW_SECRET,
        tool_name="update_project",
        idempotency_key="gateway-project-update-0001",
        request={
            "project_id": project_id,
            "expected_version": 4,
            "enabled": True,
        },
        now=NOW,
    )

    assert claim.outcome == "reserved"
    assert claim.event.session_id == session.id
    assert claim.event.tool_name == "update_project"
    assert claim.event.capability == "update_project"
    assert claim.event.request_summary_json == {
        "enabled": True,
        "expected_version": 4,
        "project_id": str(project_id),
    }


def test_missing_session_and_bad_secret_have_one_non_oracular_error(db_session) -> None:
    session = _persist_session(db_session)
    errors: list[SessionAuthenticationError] = []

    for session_id, raw_secret in (
        (uuid4(), RAW_SECRET),
        (session.id, "wrong-agent-action-secret"),
    ):
        with pytest.raises(SessionAuthenticationError) as raised:
            authorize_and_reserve_agent_action(
                db_session,
                session_id=session_id,
                raw_session_secret=raw_secret,
                tool_name="run_project",
                idempotency_key="gateway-authentication-0001",
                request={"project_id": uuid4(), "expected_version": 1},
                now=NOW,
            )
        errors.append(raised.value)

    assert {type(error) for error in errors} == {SessionAuthenticationError}
    assert {error.code for error in errors} == {"session_authentication_failed"}
    assert {str(error) for error in errors} == {"Agent session authentication failed."}
    assert _action_count(db_session) == 0


@pytest.mark.parametrize("status", ["pending", "revoked"])
def test_gateway_denies_nonapproved_session(db_session, status: str) -> None:
    session = _persist_session(db_session, status=status)

    with pytest.raises(SessionStateError, match=status):
        authorize_and_reserve_agent_action(
            db_session,
            session_id=session.id,
            raw_session_secret=RAW_SECRET,
            tool_name="run_project",
            idempotency_key=f"gateway-{status}-session-0001",
            request={"project_id": uuid4(), "expected_version": 1},
            now=NOW,
        )

    assert _action_count(db_session) == 0


def test_gateway_materializes_expiration_before_denial(db_session) -> None:
    session = _persist_session(db_session, expires_at=NOW)
    original_version = session.version

    with pytest.raises(SessionStateError, match="expired"):
        authorize_and_reserve_agent_action(
            db_session,
            session_id=session.id,
            raw_session_secret=RAW_SECRET,
            tool_name="run_project",
            idempotency_key="gateway-expired-session-0001",
            request={"project_id": uuid4(), "expected_version": 1},
            now=NOW,
        )

    assert session.status == "expired"
    assert session.expired_at == NOW
    assert session.version == original_version + 1
    assert _action_count(db_session) == 0


def test_gateway_requires_the_standard_tool_capability(db_session) -> None:
    approved = set(STANDARD_WRITE_CAPABILITIES) - {"run_project"}
    session = _persist_session(db_session, approved=approved)

    with pytest.raises(SessionCapabilityError, match="run_project"):
        authorize_and_reserve_agent_action(
            db_session,
            session_id=session.id,
            raw_session_secret=RAW_SECRET,
            tool_name="run_project",
            idempotency_key="gateway-missing-capability-0001",
            request={"project_id": uuid4(), "expected_version": 1},
            now=NOW,
        )

    assert _action_count(db_session) == 0


def test_ai_packet_request_cannot_bypass_separate_capability(db_session) -> None:
    session = _persist_session(db_session)
    thread_id = uuid4()

    with pytest.raises(ReservedAgentActionDenied) as denied:
        authorize_and_reserve_agent_action(
            db_session,
            session_id=session.id,
            raw_session_secret=RAW_SECRET,
            tool_name="create_build_packet",
            idempotency_key="gateway-ai-packet-denied-0001",
            request={
                "thread_id": thread_id,
                "expected_version": 2,
                "use_configured_ai": True,
            },
            now=NOW,
        )
    assert denied.value.claim.outcome == "reserved"
    assert denied.value.claim.event.capability == "create_build_packet"
    assert isinstance(denied.value.error, SessionCapabilityError)
    assert CONFIGURED_AI_CAPABILITY in str(denied.value.error)
    assert denied.value.claim.event.request_summary_json["use_configured_ai"] is True

    deterministic = authorize_and_reserve_agent_action(
        db_session,
        session_id=session.id,
        raw_session_secret=RAW_SECRET,
        tool_name="create_build_packet",
        idempotency_key="gateway-deterministic-packet-0001",
        request={
            "thread_id": thread_id,
            "expected_version": 2,
            "use_configured_ai": False,
        },
        now=NOW,
    )

    assert deterministic.outcome == "reserved"
    assert _action_count(db_session) == 2


@pytest.mark.parametrize("malformed", [1, 0, "true", None, []])
def test_ai_packet_request_rejects_non_boolean_capability_flag(
    db_session,
    malformed,
) -> None:
    session = _persist_session(db_session)

    with pytest.raises(InvalidAgentRequest, match="must be a boolean"):
        authorize_and_reserve_agent_action(
            db_session,
            session_id=session.id,
            raw_session_secret=RAW_SECRET,
            tool_name="create_build_packet",
            idempotency_key="gateway-ai-malformed-flag-0001",
            request={
                "thread_id": uuid4(),
                "expected_version": 2,
                "use_configured_ai": malformed,
            },
            now=NOW,
        )

    assert _action_count(db_session) == 0


def test_ai_packet_request_succeeds_only_when_both_capabilities_are_approved(
    db_session,
) -> None:
    approved = set(STANDARD_WRITE_CAPABILITIES) | {CONFIGURED_AI_CAPABILITY}
    session = _persist_session(db_session, approved=approved)

    claim = authorize_and_reserve_agent_action(
        db_session,
        session_id=session.id,
        raw_session_secret=RAW_SECRET,
        tool_name="create_build_packet",
        idempotency_key="gateway-ai-packet-approved-0001",
        request={
            "thread_id": uuid4(),
            "expected_version": 3,
            "use_configured_ai": True,
        },
        now=NOW,
    )

    assert claim.outcome == "reserved"
    assert claim.event.capability == "create_build_packet"


@pytest.mark.parametrize("tool_name", sorted(STANDARD_WRITE_CAPABILITIES))
def test_every_write_tool_requires_expected_version(db_session, tool_name: str) -> None:
    session = _persist_session(db_session)
    request = _minimum_request(tool_name)

    with pytest.raises(InvalidExpectedVersion) as raised:
        authorize_and_reserve_agent_action(
            db_session,
            session_id=session.id,
            raw_session_secret=RAW_SECRET,
            tool_name=tool_name,
            idempotency_key=f"gateway-{tool_name}-version-0001",
            request=request,
            now=NOW,
        )

    assert raised.value.code == "invalid_expected_version"
    assert _action_count(db_session) == 0


@pytest.mark.parametrize("expected_version", [0, -1, True, "1", None])
def test_expected_version_must_be_a_positive_integer(db_session, expected_version) -> None:
    session = _persist_session(db_session)

    with pytest.raises(InvalidExpectedVersion):
        authorize_and_reserve_agent_action(
            db_session,
            session_id=session.id,
            raw_session_secret=RAW_SECRET,
            tool_name="run_project",
            idempotency_key=f"gateway-invalid-version-{expected_version!s}-0001",
            request={
                "project_id": uuid4(),
                "expected_version": expected_version,
            },
            now=NOW,
        )

    assert _action_count(db_session) == 0


def test_first_agent_evidence_label_accepts_zero_expected_version(db_session) -> None:
    session = _persist_session(db_session)

    claim = authorize_and_reserve_agent_action(
        db_session,
        session_id=session.id,
        raw_session_secret=RAW_SECRET,
        tool_name="append_evidence_label",
        idempotency_key="gateway-first-label-version-zero-0001",
        request={
            "item_id": uuid4(),
            "expected_version": 0,
            "label": "unclear",
        },
        now=NOW,
    )

    assert claim.outcome == "reserved"
    assert claim.event.request_summary_json["expected_version"] == 0


def test_create_project_uses_explicit_initial_version_sentinel(db_session) -> None:
    session = _persist_session(db_session)

    with pytest.raises(InvalidExpectedVersion, match="new resource"):
        authorize_and_reserve_agent_action(
            db_session,
            session_id=session.id,
            raw_session_secret=RAW_SECRET,
            tool_name="create_project",
            idempotency_key="gateway-create-project-wrong-version-0001",
            request={"expected_version": 2, "enabled": True},
            now=NOW,
        )

    claim = authorize_and_reserve_agent_action(
        db_session,
        session_id=session.id,
        raw_session_secret=RAW_SECRET,
        tool_name="create_project",
        idempotency_key="gateway-create-project-version-one-0001",
        request={
            "expected_version": CREATE_PROJECT_EXPECTED_VERSION,
            "enabled": True,
        },
        now=NOW,
    )

    assert claim.outcome == "reserved"
    assert claim.event.request_summary_json["expected_version"] == 1


def _minimum_request(tool_name: str) -> dict[str, object]:
    if tool_name in {"update_project", "run_project"}:
        return {"project_id": uuid4()}
    if tool_name in {"set_opportunity_decision", "create_build_packet"}:
        return {"thread_id": uuid4()}
    if tool_name == "append_evidence_label":
        return {"item_id": uuid4()}
    return {}


def _persist_session(
    db_session,
    *,
    status: str = "approved",
    approved: set[str] | None = None,
    expires_at: datetime | None = None,
) -> AgentSession:
    approved_capabilities = set(STANDARD_WRITE_CAPABILITIES) if approved is None else set(approved)
    was_approved = status != "pending"
    session = AgentSession(
        client_name="Codex",
        client_version="1.0",
        process_instance_id=uuid4(),
        transport="stdio",
        secret_hash=hash_session_secret(RAW_SECRET),
        requested_capabilities_json=sorted(
            set(STANDARD_WRITE_CAPABILITIES) | {CONFIGURED_AI_CAPABILITY}
        ),
        approved_capabilities_json=(sorted(approved_capabilities) if was_approved else []),
        status=status,
        approval_source="ui" if was_approved else None,
        approved_at=NOW - timedelta(minutes=1) if was_approved else None,
        last_heartbeat_at=NOW - timedelta(seconds=60),
        expires_at=expires_at or NOW + timedelta(seconds=60),
        revoked_at=NOW if status == "revoked" else None,
        version=3 if was_approved else 1,
        created_at=NOW - timedelta(minutes=2),
        updated_at=NOW - timedelta(minutes=1),
    )
    db_session.add(session)
    db_session.flush()
    return session


def _action_count(db_session) -> int:
    return int(db_session.scalar(select(func.count()).select_from(AgentAction)) or 0)
