from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

IDEMPOTENCY_CONFLICT = "idempotency_conflict"
IDEMPOTENCY_IN_PROGRESS = "idempotency_in_progress"
IDEMPOTENCY_REPLAY = "idempotency_replay"
INVALID_ACTION_TRANSITION = "invalid_action_transition"
INVALID_AGENT_REQUEST = "invalid_agent_request"
INVALID_EXPECTED_VERSION = "invalid_expected_version"
INVALID_IDEMPOTENCY_KEY = "invalid_idempotency_key"
UNSUPPORTED_AGENT_ACTION = "unsupported_agent_action"

# Creating a project has no existing row to version-check. The MCP write contract
# therefore uses 1 as an explicit initial-resource-version sentinel, matching the
# version assigned to a newly created project.
CREATE_PROJECT_EXPECTED_VERSION = 1

MAX_IDEMPOTENCY_KEY_BYTES = 256
MIN_IDEMPOTENCY_KEY_BYTES = 8
MAX_SUMMARY_BYTES = 2_048
_SAFE_ENUM = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_SAFE_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

ClaimOutcome = Literal["reserved", "replay", "in_progress", "conflict"]


class AgentActionServiceError(ValueError):
    code = "agent_action_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidIdempotencyKey(AgentActionServiceError):
    code = INVALID_IDEMPOTENCY_KEY


class InvalidAgentRequest(AgentActionServiceError):
    code = INVALID_AGENT_REQUEST


class InvalidExpectedVersion(AgentActionServiceError):
    code = INVALID_EXPECTED_VERSION


class InvalidActionTransition(AgentActionServiceError):
    code = INVALID_ACTION_TRANSITION


class UnsupportedAgentAction(AgentActionServiceError):
    code = UNSUPPORTED_AGENT_ACTION


class ReservedAgentActionDenied(RuntimeError):
    """Authenticated authorization denial after an audit reservation exists."""

    def __init__(self, claim: ActionClaim, error: Exception) -> None:
        super().__init__("reserved_agent_action_denied")
        self.claim = claim
        self.error = error


@dataclass(frozen=True)
class ActionClaim:
    operation_id: UUID
    correlation_id: UUID
    event: Any
    outcome: ClaimOutcome
    error_code: str | None = None
    replay_result: dict[str, Any] | None = None
    replay_error_code: str | None = None


@dataclass(frozen=True)
class _FieldSpec:
    kind: Literal["bool", "enum", "id", "integer"]


_ID = _FieldSpec("id")
_INTEGER = _FieldSpec("integer")
_BOOL = _FieldSpec("bool")
_ENUM = _FieldSpec("enum")

_REQUEST_FIELDS: dict[str, dict[str, _FieldSpec]] = {
    "create_project": {
        "expected_version": _INTEGER,
        "source_id": _ID,
        "source_type": _ENUM,
        "cadence": _ENUM,
        "limit": _INTEGER,
        "enabled": _BOOL,
    },
    "update_project": {
        "project_id": _ID,
        "expected_version": _INTEGER,
        "source_id": _ID,
        "source_type": _ENUM,
        "cadence": _ENUM,
        "limit": _INTEGER,
        "enabled": _BOOL,
    },
    "run_project": {
        "project_id": _ID,
        "expected_version": _INTEGER,
        "limit": _INTEGER,
    },
    "set_opportunity_decision": {
        "thread_id": _ID,
        "expected_version": _INTEGER,
        "review_state": _ENUM,
    },
    "append_evidence_label": {
        "item_id": _ID,
        "expected_version": _INTEGER,
        "label": _ENUM,
    },
    "create_build_packet": {
        "thread_id": _ID,
        "expected_version": _INTEGER,
        "generation_mode": _ENUM,
        "use_configured_ai": _BOOL,
    },
}

_COMMON_RESULT_FIELDS: dict[str, _FieldSpec] = {
    "id": _ID,
    "project_id": _ID,
    "run_id": _ID,
    "thread_id": _ID,
    "snapshot_id": _ID,
    "item_id": _ID,
    "packet_id": _ID,
    "session_id": _ID,
    "source_id": _ID,
    "version": _INTEGER,
    "expected_version": _INTEGER,
    "current_version": _INTEGER,
    "sequence": _INTEGER,
    "artifact_count": _INTEGER,
    "items_found": _INTEGER,
    "items_saved": _INTEGER,
    "signals_detected": _INTEGER,
    "clusters_created": _INTEGER,
    "opportunities_created": _INTEGER,
    "enabled": _BOOL,
    "status": _ENUM,
    "review_state": _ENUM,
    "label": _ENUM,
    "source_type": _ENUM,
    "cadence": _ENUM,
    "generation_mode": _ENUM,
    "enhancement_status": _ENUM,
}

_TARGETS: dict[str, tuple[str, str]] = {
    "update_project": ("research_project", "project_id"),
    "run_project": ("research_project", "project_id"),
    "set_opportunity_decision": ("opportunity_thread", "thread_id"),
    "append_evidence_label": ("evidence_item", "item_id"),
    "create_build_packet": ("opportunity_thread", "thread_id"),
}


def _canonical_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Canonical requests cannot contain non-finite numbers.")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Canonical request objects require string keys.")
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonical_value(entry) for entry in value]
    raise TypeError(f"Unsupported canonical request value: {type(value).__name__}.")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def canonical_request_hash(
    tool_name: str,
    request: Mapping[str, Any] | Any,
    *,
    capability: str | None = None,
) -> str:
    envelope = {
        "capability": capability or tool_name,
        "request": request,
        "tool_name": tool_name,
    }
    return hashlib.sha256(b"tasksignal:agent-request:v1\0" + _canonical_json(envelope)).hexdigest()


def hash_idempotency_key(session_id: UUID, raw_key: str) -> str:
    if not isinstance(raw_key, str):
        raise InvalidIdempotencyKey("The idempotency key is invalid.")
    encoded = raw_key.encode()
    if (
        raw_key != raw_key.strip()
        or len(encoded) < MIN_IDEMPOTENCY_KEY_BYTES
        or len(encoded) > MAX_IDEMPOTENCY_KEY_BYTES
        or any(ord(character) < 0x21 or ord(character) == 0x7F for character in raw_key)
    ):
        raise InvalidIdempotencyKey("The idempotency key is invalid.")
    return hashlib.sha256(
        b"tasksignal:idempotency-key:v1\0" + session_id.bytes + b"\0" + encoded
    ).hexdigest()


def _safe_value(value: Any, spec: _FieldSpec) -> Any | None:
    if spec.kind == "bool":
        return value if isinstance(value, bool) else None
    if spec.kind == "integer":
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    if spec.kind == "id":
        try:
            return str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            return None
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, str) and _SAFE_ENUM.fullmatch(value):
        return value
    return None


def _bounded_allowlisted_summary(
    value: Mapping[str, Any] | Any,
    fields: Mapping[str, _FieldSpec],
) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not isinstance(value, Mapping):
        return {}
    summary: dict[str, Any] = {}
    for field_name in sorted(fields):
        if field_name not in value:
            continue
        safe = _safe_value(value[field_name], fields[field_name])
        if safe is not None:
            summary[field_name] = safe
    if len(_canonical_json(summary)) > MAX_SUMMARY_BYTES:
        return {}
    return summary


def summarize_request(tool_name: str, request: Mapping[str, Any] | Any) -> dict[str, Any]:
    return _bounded_allowlisted_summary(request, _REQUEST_FIELDS.get(tool_name, {}))


def summarize_result(tool_name: str, result: Mapping[str, Any] | Any) -> dict[str, Any]:
    del tool_name  # All result fields are response-safe scalar contract fields.
    return _bounded_allowlisted_summary(result, _COMMON_RESULT_FIELDS)


def _validate_action_contract(tool_name: str, capability: str) -> None:
    if tool_name not in _REQUEST_FIELDS:
        raise UnsupportedAgentAction("The requested agent action is not supported.")
    allowed_capabilities = {tool_name}
    if tool_name == "create_build_packet":
        allowed_capabilities.add("use_configured_ai")
    if capability not in allowed_capabilities:
        raise UnsupportedAgentAction("The requested agent action is not supported.")


def _request_data(request: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if hasattr(request, "model_dump"):
        request = request.model_dump(mode="python")
    if not isinstance(request, Mapping):
        raise InvalidExpectedVersion("Agent write requests require an expected_version.")
    return request


def _validate_expected_version(
    tool_name: str,
    request: Mapping[str, Any] | Any,
) -> None:
    request_data = _request_data(request)
    expected_version = request_data.get("expected_version")
    minimum_version = 0 if tool_name == "append_evidence_label" else 1
    if (
        not isinstance(expected_version, int)
        or isinstance(expected_version, bool)
        or expected_version < minimum_version
    ):
        qualifier = "non-negative" if minimum_version == 0 else "positive"
        raise InvalidExpectedVersion(
            f"Agent write expected_version must be a {qualifier} integer."
        )
    if tool_name == "create_project" and expected_version != CREATE_PROJECT_EXPECTED_VERSION:
        raise InvalidExpectedVersion(
            "create_project expected_version must be 1 for a new resource."
        )


def redacted_agent_action(event: Any) -> dict[str, Any]:
    """Return an audit-safe projection, even for legacy or manually altered rows."""

    tool_name = event.tool_name if event.tool_name in _REQUEST_FIELDS else "unsupported"
    capability = (
        event.capability
        if event.capability in set(_REQUEST_FIELDS) | {"use_configured_ai"}
        else "unsupported"
    )
    event_status = (
        event.event_status
        if event.event_status
        in {"reserved", "succeeded", "failed", "conflict", "replayed", "denied"}
        else "failed"
    )
    error_code = (
        event.error_code
        if isinstance(event.error_code, str) and _SAFE_ERROR_CODE.fullmatch(event.error_code)
        else None
    )
    target_type, target_id = _target_for(
        tool_name,
        summarize_request(tool_name, event.request_summary_json),
    )
    created_at = event.created_at
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    return {
        "id": str(event.id),
        "session_id": str(event.session_id),
        "operation_id": str(event.operation_id),
        "correlation_id": (str(event.correlation_id) if event.correlation_id is not None else None),
        "event_sequence": event.event_sequence,
        "event_status": event_status,
        "capability": capability,
        "tool_name": tool_name,
        "target_type": target_type,
        "target_id": target_id,
        "request_summary": summarize_request(tool_name, event.request_summary_json),
        "result_summary": (
            summarize_result(tool_name, event.result_summary_json)
            if event.result_summary_json is not None
            else None
        ),
        "error_code": error_code,
        "created_at": created_at,
    }


def _target_for(
    tool_name: str, request_summary: Mapping[str, Any]
) -> tuple[str | None, str | None]:
    target = _TARGETS.get(tool_name)
    if target is None:
        return None, None
    target_type, id_field = target
    raw_id = request_summary.get(id_field)
    return target_type, raw_id if isinstance(raw_id, str) else None


def _action_model():
    from app.models.all_models import AgentAction

    return AgentAction


def _new_event(
    *,
    session_id: UUID,
    operation_id: UUID,
    correlation_id: UUID,
    event_sequence: int,
    event_status: str,
    idempotency_key_hash: str,
    request_hash: str,
    capability: str,
    tool_name: str,
    target_type: str | None,
    target_id: str | None,
    request_summary: dict[str, Any],
    result_summary: dict[str, Any] | None,
    error_code: str | None,
    created_at: datetime,
):
    AgentAction = _action_model()
    return AgentAction(
        session_id=session_id,
        operation_id=operation_id,
        correlation_id=correlation_id,
        event_sequence=event_sequence,
        event_status=event_status,
        idempotency_key_hash=idempotency_key_hash,
        request_hash=request_hash,
        capability=capability,
        tool_name=tool_name,
        target_type=target_type,
        target_id=target_id,
        request_summary_json=request_summary,
        result_summary_json=result_summary,
        error_code=error_code,
        created_at=created_at,
    )


def _reserved_for_key(db: Session, session_id: UUID, key_hash: str) -> Any | None:
    AgentAction = _action_model()
    return db.scalar(
        select(AgentAction).where(
            AgentAction.session_id == session_id,
            AgentAction.idempotency_key_hash == key_hash,
            AgentAction.event_status == "reserved",
        )
    )


def _core_terminal_event(db: Session, operation_id: UUID) -> Any | None:
    AgentAction = _action_model()
    return db.scalar(
        select(AgentAction)
        .where(
            AgentAction.operation_id == operation_id,
            AgentAction.event_status.in_(("succeeded", "failed", "denied")),
        )
        .order_by(AgentAction.event_sequence)
        .limit(1)
    )


def _lock_reserved_operation(db: Session, operation_id: UUID) -> Any:
    AgentAction = _action_model()
    with db.no_autoflush:
        reserved = db.scalar(
            select(AgentAction)
            .where(
                AgentAction.operation_id == operation_id,
                AgentAction.event_status == "reserved",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    if reserved is None:
        raise InvalidActionTransition("The action reservation no longer exists.")
    return reserved


def _next_event_sequence(db: Session, operation_id: UUID) -> int:
    AgentAction = _action_model()
    current = db.scalar(
        select(func.max(AgentAction.event_sequence)).where(AgentAction.operation_id == operation_id)
    )
    return int(current or 0) + 1


def _lock_agent_session(db: Session, session_id: UUID) -> Any | None:
    from app.models.all_models import AgentSession

    with db.no_autoflush:
        return db.scalar(
            select(AgentSession)
            .where(AgentSession.id == session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )


def _authorize_agent_action_session(
    db: Session,
    *,
    session_id: UUID,
    raw_session_secret: str,
    tool_name: str,
    request: Mapping[str, Any] | Any,
    now: datetime | None = None,
    require_configured_ai: bool = True,
) -> Any:
    """Authenticate and authorize one MCP write while locking its session.

    The capability is deliberately derived from ``tool_name`` rather than accepted
    from the caller. Authentication, lease state, all required capabilities, and
    optimistic-version shape are checked while the transaction owns the database
    write lock. The caller must hold this transaction through the domain commit.
    """

    from app.services.agent_sessions.service import (
        CONFIGURED_AI_CAPABILITY,
        SessionAuthenticationError,
        expire_session_if_needed,
        require_capability,
        verify_session_secret,
    )
    from app.workers.scan_pipeline import acquire_database_scan_write_lock_with_retry

    _validate_action_contract(tool_name, tool_name)
    timestamp = now or datetime.now(UTC)
    # SQLite ignores SELECT .. FOR UPDATE, so acquire its immediate write lock
    # before loading the session. PostgreSQL then adds a row lock below. Holding
    # this transaction through the domain mutation prevents revoke/write races.
    acquire_database_scan_write_lock_with_retry(db)
    session = _lock_agent_session(db, session_id)

    # Hash even when the UUID misses so missing IDs and bad secrets share the same
    # public error and approximately the same authentication work.
    stored_hash = session.secret_hash if session is not None else "0" * 64
    authenticated = verify_session_secret(raw_session_secret, stored_hash)
    if session is None or not authenticated:
        raise SessionAuthenticationError("Agent session authentication failed.")

    # Keep a materialized terminal state in the unit of work so the caller's error
    # boundary can commit it while returning the authorization denial.
    expire_session_if_needed(session, now=timestamp)
    require_capability(session, tool_name, now=timestamp)

    request_data = _request_data(request)
    if tool_name == "create_build_packet":
        use_configured_ai = request_data.get("use_configured_ai", False)
        if not isinstance(use_configured_ai, bool):
            raise InvalidAgentRequest("use_configured_ai must be a boolean.")
        if use_configured_ai and require_configured_ai:
            require_capability(session, CONFIGURED_AI_CAPABILITY, now=timestamp)
    _validate_expected_version(tool_name, request_data)
    return session


def _authorize_and_reserve_agent_action(
    db: Session,
    *,
    session_id: UUID,
    raw_session_secret: str,
    tool_name: str,
    idempotency_key: str,
    request: Mapping[str, Any] | Any,
    correlation_id: UUID | None = None,
    now: datetime | None = None,
) -> ActionClaim:
    """Authorize one MCP write and reserve its append-only audit operation."""

    timestamp = now or datetime.now(UTC)
    session = _authorize_agent_action_session(
        db,
        session_id=session_id,
        raw_session_secret=raw_session_secret,
        tool_name=tool_name,
        request=request,
        now=timestamp,
        require_configured_ai=False,
    )

    claim = _reserve_agent_action(
        db,
        session_id=session.id,
        capability=tool_name,
        tool_name=tool_name,
        idempotency_key=idempotency_key,
        request=request,
        correlation_id=correlation_id,
        now=timestamp,
    )
    if claim.outcome == "reserved" and tool_name == "create_build_packet":
        request_data = _request_data(request)
        if request_data.get("use_configured_ai", False):
            from app.services.agent_sessions.service import (
                CONFIGURED_AI_CAPABILITY,
                AgentSessionError,
                require_capability,
            )

            try:
                require_capability(
                    session,
                    CONFIGURED_AI_CAPABILITY,
                    now=timestamp,
                )
            except AgentSessionError as exc:
                raise ReservedAgentActionDenied(claim, exc) from exc
    return claim


def _reserve_agent_action(
    db: Session,
    *,
    session_id: UUID,
    capability: str,
    tool_name: str,
    idempotency_key: str,
    request: Mapping[str, Any] | Any,
    correlation_id: UUID | None = None,
    now: datetime | None = None,
) -> ActionClaim:
    """Low-level ledger primitive; callers must use the authorized executor."""
    _validate_action_contract(tool_name, capability)
    created_at = now or datetime.now(UTC)
    correlation = correlation_id or uuid4()
    key_hash = hash_idempotency_key(session_id, idempotency_key)
    request_hash = canonical_request_hash(tool_name, request, capability=capability)
    request_summary = summarize_request(tool_name, request)
    existing = _reserved_for_key(db, session_id, key_hash)
    if existing is None:
        operation_id = uuid4()
        target_type, target_id = _target_for(tool_name, request_summary)
        reserved = _new_event(
            session_id=session_id,
            operation_id=operation_id,
            correlation_id=correlation,
            event_sequence=1,
            event_status="reserved",
            idempotency_key_hash=key_hash,
            request_hash=request_hash,
            capability=capability,
            tool_name=tool_name,
            target_type=target_type,
            target_id=target_id,
            request_summary=request_summary,
            result_summary=None,
            error_code=None,
            created_at=created_at,
        )
        try:
            # The partial unique reservation index is the final arbiter when two
            # requests with the same key arrive concurrently. A savepoint keeps the
            # caller's domain transaction usable after the losing insert rolls back.
            with db.begin_nested():
                db.add(reserved)
                db.flush()
        except IntegrityError:
            existing = _reserved_for_key(db, session_id, key_hash)
            if existing is None:
                raise
        else:
            return ActionClaim(
                operation_id=operation_id,
                correlation_id=correlation,
                event=reserved,
                outcome="reserved",
            )

    if existing.request_hash != request_hash:
        collision = _append_attempt_event(
            db,
            reserved=existing,
            correlation_id=correlation,
            event_status="conflict",
            error_code=IDEMPOTENCY_CONFLICT,
            result_summary=None,
            created_at=created_at,
        )
        return ActionClaim(
            operation_id=existing.operation_id,
            correlation_id=correlation,
            event=collision,
            outcome="conflict",
            error_code=IDEMPOTENCY_CONFLICT,
        )

    terminal = _core_terminal_event(db, existing.operation_id)
    if terminal is None:
        replay_event = _append_attempt_event(
            db,
            reserved=existing,
            correlation_id=correlation,
            event_status="replayed",
            error_code=IDEMPOTENCY_IN_PROGRESS,
            result_summary=None,
            created_at=created_at,
        )
        return ActionClaim(
            operation_id=existing.operation_id,
            correlation_id=correlation,
            event=replay_event,
            outcome="in_progress",
            error_code=IDEMPOTENCY_IN_PROGRESS,
        )

    replay_event = _append_attempt_event(
        db,
        reserved=existing,
        correlation_id=correlation,
        event_status="replayed",
        error_code=IDEMPOTENCY_REPLAY,
        result_summary=(
            summarize_result(existing.tool_name, terminal.result_summary_json)
            if terminal.result_summary_json is not None
            else None
        ),
        created_at=created_at,
    )
    return ActionClaim(
        operation_id=existing.operation_id,
        correlation_id=correlation,
        event=replay_event,
        outcome="replay",
        error_code=IDEMPOTENCY_REPLAY,
        replay_result=(
            summarize_result(existing.tool_name, terminal.result_summary_json)
            if terminal.result_summary_json is not None
            else None
        ),
        replay_error_code=(
            terminal.error_code
            if isinstance(terminal.error_code, str)
            and _SAFE_ERROR_CODE.fullmatch(terminal.error_code)
            else None
        ),
    )


def _append_attempt_event(
    db: Session,
    *,
    reserved: Any,
    correlation_id: UUID,
    event_status: str,
    error_code: str | None,
    result_summary: dict[str, Any] | None,
    created_at: datetime,
) -> Any:
    reserved = _lock_reserved_operation(db, reserved.operation_id)
    event = _new_event(
        session_id=reserved.session_id,
        operation_id=reserved.operation_id,
        correlation_id=correlation_id,
        event_sequence=_next_event_sequence(db, reserved.operation_id),
        event_status=event_status,
        idempotency_key_hash=reserved.idempotency_key_hash,
        request_hash=reserved.request_hash,
        capability=reserved.capability,
        tool_name=reserved.tool_name,
        target_type=reserved.target_type,
        target_id=reserved.target_id,
        request_summary=summarize_request(reserved.tool_name, reserved.request_summary_json),
        result_summary=(
            summarize_result(reserved.tool_name, result_summary)
            if result_summary is not None
            else None
        ),
        error_code=error_code,
        created_at=created_at,
    )
    db.add(event)
    db.flush()
    return event


def _append_terminal(
    db: Session,
    *,
    claim: ActionClaim,
    event_status: Literal["succeeded", "failed", "denied"],
    result: Mapping[str, Any] | Any,
    error_code: str | None,
    now: datetime | None,
) -> Any:
    if claim.outcome != "reserved":
        raise InvalidActionTransition("Only a newly reserved action may become terminal.")
    reserved = _lock_reserved_operation(db, claim.operation_id)
    existing_terminal = _core_terminal_event(db, claim.operation_id)
    if existing_terminal is not None:
        raise InvalidActionTransition("The action already has a terminal event.")
    if error_code is not None and not _SAFE_ERROR_CODE.fullmatch(error_code):
        raise ValueError("The action error code is invalid.")
    terminal = _new_event(
        session_id=reserved.session_id,
        operation_id=claim.operation_id,
        correlation_id=claim.correlation_id,
        event_sequence=_next_event_sequence(db, claim.operation_id),
        event_status=event_status,
        idempotency_key_hash=reserved.idempotency_key_hash,
        request_hash=reserved.request_hash,
        capability=reserved.capability,
        tool_name=reserved.tool_name,
        target_type=reserved.target_type,
        target_id=reserved.target_id,
        request_summary=summarize_request(reserved.tool_name, reserved.request_summary_json),
        result_summary=summarize_result(reserved.tool_name, result),
        error_code=error_code,
        created_at=now or datetime.now(UTC),
    )
    try:
        with db.begin_nested():
            db.add(terminal)
            db.flush()
    except IntegrityError as exc:
        if _core_terminal_event(db, claim.operation_id) is not None:
            raise InvalidActionTransition("The action already has a terminal event.") from exc
        raise
    return terminal


def complete_agent_action(
    db: Session,
    *,
    claim: ActionClaim,
    result: Mapping[str, Any] | Any,
    now: datetime | None = None,
) -> Any:
    return _append_terminal(
        db,
        claim=claim,
        event_status="succeeded",
        result=result,
        error_code=None,
        now=now,
    )


def fail_agent_action(
    db: Session,
    *,
    claim: ActionClaim,
    error_code: str,
    result: Mapping[str, Any] | Any,
    now: datetime | None = None,
) -> Any:
    return _append_terminal(
        db,
        claim=claim,
        event_status="failed",
        result=result,
        error_code=error_code,
        now=now,
    )


def deny_agent_action(
    db: Session,
    *,
    claim: ActionClaim,
    error_code: str,
    result: Mapping[str, Any] | Any = None,
    now: datetime | None = None,
) -> Any:
    return _append_terminal(
        db,
        claim=claim,
        event_status="denied",
        result=result,
        error_code=error_code,
        now=now,
    )
