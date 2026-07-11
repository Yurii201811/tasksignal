from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.services.agent_sessions.service import (
    CONFIGURED_AI_CAPABILITY,
    STANDARD_WRITE_CAPABILITIES,
    AgentSessionError,
    InvalidSessionSecretHash,
    SessionAuthenticationError,
    SessionCapabilityError,
    SessionNotFound,
    SessionStateError,
    SessionVersionConflict,
    approve_session,
    authenticate_session,
    effective_session_status,
    hash_session_secret,
    heartbeat_session,
    mark_session_exited,
    register_session,
    require_capability,
    revoke_session,
)

NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
RAW_SECRET = "session-process-secret-with-at-least-32-bytes"
PROCESS_INSTANCE_ID = UUID("761b64fa-2dc2-4fd1-8c29-331f6e4ac7fc")


@dataclass
class FakeAgentSession:
    client_name: str
    process_instance_id: UUID
    transport: str
    secret_hash: str
    requested_capabilities_json: list[str]
    status: str
    last_heartbeat_at: datetime
    expires_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime
    client_version: str | None = None
    approved_capabilities_json: list[str] = field(default_factory=list)
    approval_source: str | None = None
    approved_at: datetime | None = None
    revoked_at: datetime | None = None
    expired_at: datetime | None = None
    exited_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)


class FakeDatabase:
    def __init__(self) -> None:
        self.added: list[FakeAgentSession] = []
        self.flushed = False
        self.sessions: dict[UUID, FakeAgentSession] = {}

    def add(self, session: FakeAgentSession) -> None:
        self.added.append(session)
        self.sessions[session.id] = session

    def flush(self) -> None:
        self.flushed = True

    def get(self, _model: type[object], session_id: UUID) -> FakeAgentSession | None:
        return self.sessions.get(session_id)


def make_session(
    *,
    status: str = "pending",
    requested: set[str] | frozenset[str] | None = None,
    approved: set[str] | frozenset[str] | None = None,
    expires_at: datetime | None = None,
    version: int = 1,
) -> FakeAgentSession:
    return FakeAgentSession(
        client_name="Codex",
        client_version="1.0",
        process_instance_id=PROCESS_INSTANCE_ID,
        transport="stdio",
        secret_hash=hash_session_secret(RAW_SECRET),
        requested_capabilities_json=sorted(requested or STANDARD_WRITE_CAPABILITIES),
        approved_capabilities_json=sorted(approved or set()),
        status=status,
        last_heartbeat_at=NOW,
        expires_at=expires_at or NOW + timedelta(seconds=60),
        version=version,
        created_at=NOW,
        updated_at=NOW,
    )


def test_hash_session_secret_is_stable_and_never_returns_raw_secret() -> None:
    digest = hash_session_secret(RAW_SECRET)

    assert len(digest) == 64
    assert digest == digest.lower()
    assert RAW_SECRET not in digest
    assert digest == hash_session_secret(RAW_SECRET)


@pytest.mark.parametrize("value", ["", "short", "a" * 63, "g" * 64, "A" * 64])
def test_registration_rejects_invalid_caller_generated_secret_hash(value: str) -> None:
    db = FakeDatabase()

    with pytest.raises(InvalidSessionSecretHash):
        register_session(
            db,
            session_factory=FakeAgentSession,
            secret_hash=value,
            client_name="Codex",
            client_version="1.0",
            process_instance_id=PROCESS_INSTANCE_ID,
            requested_capabilities=STANDARD_WRITE_CAPABILITIES,
            now=NOW,
        )


def test_registration_persists_only_the_caller_generated_hash() -> None:
    db = FakeDatabase()
    digest = hash_session_secret(RAW_SECRET)

    session = register_session(
        db,
        session_factory=FakeAgentSession,
        secret_hash=digest,
        client_name="Codex",
        client_version="1.0",
        process_instance_id=str(PROCESS_INSTANCE_ID),
        requested_capabilities=STANDARD_WRITE_CAPABILITIES | {CONFIGURED_AI_CAPABILITY},
        now=NOW,
    )

    assert db.added == [session]
    assert db.flushed is True
    assert session.secret_hash == digest
    assert session.process_instance_id == PROCESS_INSTANCE_ID
    assert not hasattr(session, "raw_secret")
    assert session.status == "pending"
    assert session.last_heartbeat_at == NOW
    assert session.expires_at == NOW + timedelta(seconds=60)
    assert session.expired_at is None
    assert session.version == 1


def test_registration_round_trips_through_the_agent_session_orm(db_session) -> None:
    from app.models.all_models import AgentSession

    digest = hash_session_secret(RAW_SECRET)
    session = register_session(
        db_session,
        secret_hash=digest,
        client_name="Codex",
        client_version="1.0",
        process_instance_id=PROCESS_INSTANCE_ID,
        requested_capabilities=STANDARD_WRITE_CAPABILITIES,
        now=NOW,
    )
    session_id = session.id
    db_session.commit()
    db_session.expire_all()

    stored = db_session.get(AgentSession, session_id)
    assert stored is not None
    assert stored.secret_hash == digest
    assert stored.process_instance_id == PROCESS_INSTANCE_ID
    assert stored.requested_capabilities_json == sorted(STANDARD_WRITE_CAPABILITIES)
    assert stored.approved_capabilities_json == []
    assert "raw_secret" not in stored.__dict__


def test_registration_requires_the_complete_standard_write_set() -> None:
    db = FakeDatabase()
    incomplete = set(STANDARD_WRITE_CAPABILITIES) - {"create_build_packet"}

    with pytest.raises(SessionCapabilityError, match="complete standard write set"):
        register_session(
            db,
            session_factory=FakeAgentSession,
            secret_hash=hash_session_secret(RAW_SECRET),
            client_name="Codex",
            process_instance_id=PROCESS_INSTANCE_ID,
            requested_capabilities=incomplete,
            now=NOW,
        )


@pytest.mark.parametrize("value", ["", "process-123", "{761b64fa-2dc2-4fd1-8c29-331f6e4ac7fc}"])
def test_registration_rejects_noncanonical_process_instance_ids(value: str) -> None:
    with pytest.raises(AgentSessionError, match="process_instance_id"):
        register_session(
            FakeDatabase(),
            session_factory=FakeAgentSession,
            secret_hash=hash_session_secret(RAW_SECRET),
            client_name="Codex",
            process_instance_id=value,
            requested_capabilities=STANDARD_WRITE_CAPABILITIES,
            now=NOW,
        )


def test_authentication_returns_session_for_matching_process_secret() -> None:
    db = FakeDatabase()
    session = make_session(status="expired")
    db.add(session)

    authenticated = authenticate_session(
        db,
        session_id=session.id,
        raw_secret=RAW_SECRET,
        model_type=FakeAgentSession,
    )

    assert authenticated is session
    assert authenticated.status == "expired"


def test_authentication_hides_missing_session_and_rejects_wrong_secret() -> None:
    db = FakeDatabase()
    session = make_session()
    db.add(session)

    with pytest.raises(SessionNotFound, match="not found or could not be authenticated"):
        authenticate_session(
            db,
            session_id=uuid4(),
            raw_secret=RAW_SECRET,
            model_type=FakeAgentSession,
        )
    with pytest.raises(
        SessionAuthenticationError,
        match="not found or could not be authenticated",
    ):
        authenticate_session(
            db,
            session_id=session.id,
            raw_secret="wrong-session-secret",
            model_type=FakeAgentSession,
        )


def test_effective_status_expires_at_the_exact_sixty_second_boundary() -> None:
    session = make_session()

    assert (
        effective_session_status(session, now=NOW + timedelta(seconds=59, microseconds=999999))
        == "pending"
    )
    assert effective_session_status(session, now=NOW + timedelta(seconds=60)) == "expired"


def test_approval_grants_all_standard_writes_but_not_ai_by_default() -> None:
    requested = STANDARD_WRITE_CAPABILITIES | {CONFIGURED_AI_CAPABILITY}
    session = make_session(requested=requested)

    approve_session(
        session,
        expected_version=1,
        approval_source="ui",
        include_configured_ai=False,
        now=NOW + timedelta(seconds=1),
    )

    assert session.status == "approved"
    assert set(session.approved_capabilities_json) == STANDARD_WRITE_CAPABILITIES
    assert CONFIGURED_AI_CAPABILITY not in session.approved_capabilities_json
    assert session.approved_at == NOW + timedelta(seconds=1)
    assert session.approval_source == "ui"
    assert session.version == 2


def test_ai_capability_requires_separate_selection_and_prior_request() -> None:
    session = make_session(requested=STANDARD_WRITE_CAPABILITIES)

    with pytest.raises(SessionCapabilityError, match="not requested"):
        approve_session(
            session,
            expected_version=1,
            approval_source="interactive_tty",
            include_configured_ai=True,
            now=NOW + timedelta(seconds=1),
        )

    assert session.status == "pending"
    assert session.version == 1


def test_ai_capability_is_granted_only_when_separately_selected() -> None:
    requested = STANDARD_WRITE_CAPABILITIES | {CONFIGURED_AI_CAPABILITY}
    session = make_session(requested=requested)

    approve_session(
        session,
        expected_version=1,
        approval_source="interactive_tty",
        include_configured_ai=True,
        now=NOW + timedelta(seconds=1),
    )

    assert set(session.approved_capabilities_json) == requested


def test_approval_rejects_expired_and_stale_sessions() -> None:
    expired = make_session(expires_at=NOW)
    stale = make_session(version=3)

    with pytest.raises(SessionStateError, match="expired"):
        approve_session(
            expired,
            expected_version=1,
            approval_source="ui",
            now=NOW,
        )
    with pytest.raises(SessionVersionConflict, match="expected 2, current 3") as conflict:
        approve_session(
            stale,
            expected_version=2,
            approval_source="ui",
            now=NOW,
        )
    assert conflict.value.code == "session_version_conflict"
    assert conflict.value.expected_version == 2
    assert conflict.value.current_version == 3


def test_heartbeat_authenticates_and_renews_from_heartbeat_time() -> None:
    session = make_session(status="approved", approved=STANDARD_WRITE_CAPABILITIES)
    heartbeat_at = NOW + timedelta(seconds=30)

    heartbeat_session(session, raw_secret=RAW_SECRET, now=heartbeat_at)

    assert session.last_heartbeat_at == heartbeat_at
    assert session.expires_at == heartbeat_at + timedelta(seconds=60)
    assert session.version == 2


def test_heartbeat_rejects_wrong_secret_without_changing_lease() -> None:
    session = make_session()

    with pytest.raises(SessionAuthenticationError):
        heartbeat_session(
            session, raw_secret="wrong-session-secret", now=NOW + timedelta(seconds=30)
        )

    assert session.last_heartbeat_at == NOW
    assert session.expires_at == NOW + timedelta(seconds=60)
    assert session.version == 1


@pytest.mark.parametrize("status", ["revoked", "expired", "exited"])
def test_heartbeat_cannot_revive_terminal_session(status: str) -> None:
    session = make_session(status=status)

    with pytest.raises(SessionStateError, match=status):
        heartbeat_session(session, raw_secret=RAW_SECRET, now=NOW + timedelta(seconds=1))

    assert session.status == status
    assert session.version == 1


def test_heartbeat_cannot_revive_effectively_expired_session() -> None:
    session = make_session(status="approved", expires_at=NOW)

    with pytest.raises(SessionStateError, match="expired"):
        heartbeat_session(session, raw_secret=RAW_SECRET, now=NOW)

    assert effective_session_status(session, now=NOW) == "expired"
    assert session.status == "expired"
    assert session.expired_at == NOW
    assert session.last_heartbeat_at == NOW
    assert session.expires_at == NOW


def test_revoke_and_exit_are_terminal_and_do_not_get_overwritten() -> None:
    revoked = make_session(status="approved", approved=STANDARD_WRITE_CAPABILITIES)
    exited = make_session(status="approved", approved=STANDARD_WRITE_CAPABILITIES)

    revoke_session(revoked, expected_version=1, now=NOW + timedelta(seconds=1))
    mark_session_exited(exited, now=NOW + timedelta(seconds=1))

    assert revoked.status == "revoked"
    assert revoked.revoked_at == NOW + timedelta(seconds=1)
    assert exited.status == "exited"
    assert exited.exited_at == NOW + timedelta(seconds=1)
    with pytest.raises(SessionStateError, match="revoked"):
        mark_session_exited(revoked, now=NOW + timedelta(seconds=2))
    with pytest.raises(SessionStateError, match="exited"):
        revoke_session(exited, expected_version=2, now=NOW + timedelta(seconds=2))


def test_require_capability_enforces_state_and_separate_ai_permission() -> None:
    approved = make_session(status="approved", approved=STANDARD_WRITE_CAPABILITIES)
    pending = make_session()

    require_capability(approved, "create_project", now=NOW)
    with pytest.raises(SessionCapabilityError, match=CONFIGURED_AI_CAPABILITY):
        require_capability(approved, CONFIGURED_AI_CAPABILITY, now=NOW)
    with pytest.raises(SessionStateError, match="pending"):
        require_capability(pending, "create_project", now=NOW)
