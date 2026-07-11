from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Collection
from datetime import UTC, datetime, timedelta
from secrets import compare_digest
from typing import Any, Literal, Protocol, TypeVar, cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.all_models import now_utc

SESSION_TTL = timedelta(seconds=60)
_SESSION_SECRET_HASH_NAMESPACE = b"tasksignal:agent-session-secret:v1\0"
CONFIGURED_AI_CAPABILITY = "use_configured_ai"
STANDARD_WRITE_CAPABILITIES = frozenset(
    {
        "append_evidence_label",
        "create_build_packet",
        "create_project",
        "run_project",
        "set_opportunity_decision",
        "update_project",
    }
)
APPROVABLE_CAPABILITIES = STANDARD_WRITE_CAPABILITIES | {CONFIGURED_AI_CAPABILITY}
TERMINAL_STATUSES = frozenset({"expired", "revoked", "exited"})
ACTIVE_STATUSES = frozenset({"pending", "approved"})
APPROVAL_SOURCES = frozenset({"ui", "interactive_tty"})
_SHA256_HEX = re.compile(r"[0-9a-f]{64}\Z")

SessionStatus = Literal["pending", "approved", "revoked", "expired", "exited"]


class AgentSessionLike(Protocol):
    id: UUID
    secret_hash: str
    status: str
    requested_capabilities_json: list[str]
    approved_capabilities_json: list[str]
    approval_source: str | None
    approved_at: datetime | None
    last_heartbeat_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    expired_at: datetime | None
    exited_at: datetime | None
    version: int
    updated_at: datetime


SessionT = TypeVar("SessionT", bound=AgentSessionLike)


class AgentSessionError(ValueError):
    """Base class for safe, expected agent-session lifecycle failures."""

    code = "agent_session_error"


class InvalidSessionSecretHash(AgentSessionError):
    code = "invalid_session_secret_hash"


class SessionNotFound(AgentSessionError):
    code = "session_authentication_failed"


class SessionAuthenticationError(AgentSessionError):
    code = "session_authentication_failed"


class SessionStateError(AgentSessionError):
    code = "session_state_error"


class SessionCapabilityError(AgentSessionError):
    code = "session_capability_error"


class SessionVersionConflict(AgentSessionError):
    code = "session_version_conflict"

    def __init__(self, *, expected_version: int, current_version: int) -> None:
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"Agent session version conflict: expected {expected_version}, "
            f"current {current_version}."
        )


def _utc(value: datetime | None = None) -> datetime:
    result = value or now_utc()
    if result.tzinfo is None:
        return result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def hash_session_secret(raw_secret: str) -> str:
    """Hash a high-entropy process secret for caller-side registration/authentication.

    MCP processes generate and retain the raw secret. The API receives only this digest
    at registration time, so the raw value never becomes ORM state, a response field, or
    an audit value.
    """

    if not isinstance(raw_secret, str):
        raise TypeError("Session secret must be a string.")
    return hashlib.sha256(_SESSION_SECRET_HASH_NAMESPACE + raw_secret.encode("utf-8")).hexdigest()


def validate_session_secret_hash(secret_hash: str) -> str:
    if not isinstance(secret_hash, str) or _SHA256_HEX.fullmatch(secret_hash) is None:
        raise InvalidSessionSecretHash(
            "Session secret hash must be a lowercase SHA-256 hexadecimal digest."
        )
    return secret_hash


def verify_session_secret(raw_secret: str, secret_hash: str) -> bool:
    if not isinstance(secret_hash, str) or _SHA256_HEX.fullmatch(secret_hash) is None:
        return False
    try:
        candidate = hash_session_secret(raw_secret)
    except (TypeError, UnicodeEncodeError):
        return False
    return compare_digest(candidate, secret_hash)


def _normalize_capabilities(capabilities: Collection[str]) -> frozenset[str]:
    if isinstance(capabilities, (str, bytes)):
        raise SessionCapabilityError("Capabilities must be a collection of names.")
    normalized = frozenset(capabilities)
    if any(not isinstance(capability, str) for capability in normalized):
        raise SessionCapabilityError("Capability names must be strings.")
    unknown = normalized - APPROVABLE_CAPABILITIES
    if unknown:
        raise SessionCapabilityError(f"Unsupported agent-session capability: {sorted(unknown)[0]}.")
    if not STANDARD_WRITE_CAPABILITIES.issubset(normalized):
        raise SessionCapabilityError("Agent sessions must request the complete standard write set.")
    return normalized


def _require_nonempty(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentSessionError(f"{field_name} must not be empty.")
    return value.strip()


def _canonical_uuid(value: UUID | str, *, field_name: str) -> UUID:
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise AgentSessionError(f"{field_name} must be a UUID.")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise AgentSessionError(f"{field_name} must be a canonical UUID.") from exc
    if value != str(parsed):
        raise AgentSessionError(f"{field_name} must be a canonical UUID.")
    return parsed


def register_session(
    db: Session | Any,
    *,
    secret_hash: str,
    client_name: str,
    process_instance_id: UUID | str,
    requested_capabilities: Collection[str],
    client_version: str | None = None,
    transport: str = "stdio",
    now: datetime | None = None,
    session_factory: Callable[..., SessionT] | None = None,
) -> SessionT:
    """Register a process-bound session from a caller-generated secret digest."""

    digest = validate_session_secret_hash(secret_hash)
    capabilities = _normalize_capabilities(requested_capabilities)
    timestamp = _utc(now)
    canonical_name = _require_nonempty(client_name, field_name="client_name")
    canonical_process_id = _canonical_uuid(
        process_instance_id,
        field_name="process_instance_id",
    )
    if transport != "stdio":
        raise AgentSessionError("Only stdio agent sessions are supported in v1.")
    if client_version is not None:
        client_version = _require_nonempty(client_version, field_name="client_version")

    if session_factory is None:
        # Delayed import keeps the pure lifecycle helpers independently testable and
        # avoids ever coupling the process-side raw secret to the ORM constructor.
        from app.models.all_models import AgentSession

        session_factory = cast(Callable[..., SessionT], AgentSession)

    session = session_factory(
        client_name=canonical_name,
        client_version=client_version,
        process_instance_id=canonical_process_id,
        transport=transport,
        secret_hash=digest,
        status="pending",
        requested_capabilities_json=sorted(capabilities),
        approved_capabilities_json=[],
        approval_source=None,
        approved_at=None,
        last_heartbeat_at=timestamp,
        expires_at=timestamp + SESSION_TTL,
        revoked_at=None,
        expired_at=None,
        exited_at=None,
        version=1,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(session)
    db.flush()
    return session


def authenticate_session(
    db: Session | Any,
    *,
    session_id: UUID,
    raw_secret: str,
    model_type: type[SessionT] | None = None,
) -> SessionT:
    """Authenticate a session without implying that its lease is active."""

    if model_type is None:
        from app.models.all_models import AgentSession

        model_type = cast(type[SessionT], AgentSession)
    session = db.get(model_type, session_id)
    if session is None:
        # Deliberately share one public error with a bad secret to avoid an ID oracle.
        raise SessionNotFound("Agent session was not found or could not be authenticated.")
    if not verify_session_secret(raw_secret, session.secret_hash):
        raise SessionAuthenticationError(
            "Agent session was not found or could not be authenticated."
        )
    return session


def effective_session_status(
    session: AgentSessionLike,
    *,
    now: datetime | None = None,
) -> SessionStatus:
    status = session.status
    if status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
        raise SessionStateError(f"Unsupported agent session state: {status}.")
    if status in ACTIVE_STATUSES and _utc(now) >= _utc(session.expires_at):
        return "expired"
    return cast(SessionStatus, status)


def expire_session_if_needed(
    session: SessionT,
    *,
    now: datetime | None = None,
) -> bool:
    timestamp = _utc(now)
    if session.status not in ACTIVE_STATUSES or timestamp < _utc(session.expires_at):
        return False
    session.status = "expired"
    session.expired_at = timestamp
    session.updated_at = timestamp
    session.version += 1
    return True


def _assert_current_version(session: AgentSessionLike, expected_version: int | None) -> None:
    if expected_version is not None and expected_version != session.version:
        raise SessionVersionConflict(
            expected_version=expected_version,
            current_version=session.version,
        )


def _require_state(
    session: SessionT,
    *,
    allowed: frozenset[str],
    now: datetime,
) -> None:
    expire_session_if_needed(session, now=now)
    if session.status not in allowed:
        raise SessionStateError(f"Agent session is {session.status}.")


def approve_session(
    session: SessionT,
    *,
    expected_version: int,
    approval_source: str,
    include_configured_ai: bool = False,
    now: datetime | None = None,
) -> SessionT:
    timestamp = _utc(now)
    _require_state(session, allowed=frozenset({"pending"}), now=timestamp)
    _assert_current_version(session, expected_version)
    if approval_source not in APPROVAL_SOURCES:
        raise AgentSessionError("Approval source must be ui or interactive_tty.")

    requested = _normalize_capabilities(session.requested_capabilities_json)
    approved = set(STANDARD_WRITE_CAPABILITIES)
    if include_configured_ai:
        if CONFIGURED_AI_CAPABILITY not in requested:
            raise SessionCapabilityError(
                f"Capability {CONFIGURED_AI_CAPABILITY} was not requested by this process."
            )
        approved.add(CONFIGURED_AI_CAPABILITY)

    session.status = "approved"
    session.approved_capabilities_json = sorted(approved)
    session.approval_source = approval_source
    session.approved_at = timestamp
    session.updated_at = timestamp
    session.version += 1
    return session


def heartbeat_session(
    session: SessionT,
    *,
    raw_secret: str,
    expected_version: int | None = None,
    now: datetime | None = None,
) -> SessionT:
    if not verify_session_secret(raw_secret, session.secret_hash):
        raise SessionAuthenticationError("Agent session could not be authenticated.")
    timestamp = _utc(now)
    _require_state(session, allowed=ACTIVE_STATUSES, now=timestamp)
    _assert_current_version(session, expected_version)

    session.last_heartbeat_at = timestamp
    session.expires_at = timestamp + SESSION_TTL
    session.updated_at = timestamp
    session.version += 1
    return session


def revoke_session(
    session: SessionT,
    *,
    expected_version: int,
    now: datetime | None = None,
) -> SessionT:
    timestamp = _utc(now)
    _require_state(session, allowed=ACTIVE_STATUSES, now=timestamp)
    _assert_current_version(session, expected_version)

    session.status = "revoked"
    session.revoked_at = timestamp
    session.updated_at = timestamp
    session.version += 1
    return session


def mark_session_exited(
    session: SessionT,
    *,
    expected_version: int | None = None,
    now: datetime | None = None,
) -> SessionT:
    timestamp = _utc(now)
    _require_state(session, allowed=ACTIVE_STATUSES, now=timestamp)
    _assert_current_version(session, expected_version)

    session.status = "exited"
    session.exited_at = timestamp
    session.updated_at = timestamp
    session.version += 1
    return session


def require_capability(
    session: AgentSessionLike,
    capability: str,
    *,
    now: datetime | None = None,
) -> None:
    if capability not in APPROVABLE_CAPABILITIES:
        raise SessionCapabilityError(f"Unsupported capability: {capability}.")
    status = effective_session_status(session, now=now)
    if status != "approved":
        raise SessionStateError(f"Agent session is {status}.")
    if capability not in set(session.approved_capabilities_json):
        raise SessionCapabilityError(f"Agent session does not have capability {capability}.")
