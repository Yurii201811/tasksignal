from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.all_models import AgentSession
from app.services.agent_actions.service import (
    IDEMPOTENCY_REPLAY,
    ActionClaim,
    AgentActionServiceError,
    InvalidActionTransition,
    ReservedAgentActionDenied,
    _authorize_agent_action_session,
    _authorize_and_reserve_agent_action,
    _core_terminal_event,
    complete_agent_action,
    deny_agent_action,
    fail_agent_action,
    summarize_result,
)
from app.services.agent_sessions import AgentSessionError
from app.workers.scan_pipeline import (
    acquire_database_scan_write_lock_with_retry,
)

TerminalStatus = Literal["failed", "denied", "in_progress"]
FailureMapper = Callable[
    [Exception],
    tuple[TerminalStatus, str, Mapping[str, Any] | Any],
]
Mutation = Callable[[Session], Any]
SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class AgentActionExecution:
    outcome: Literal["succeeded", "replay", "in_progress", "conflict"]
    operation_id: UUID
    correlation_id: UUID
    result: Any = None
    error_code: str | None = None


def _commit_materialized_expiration_or_rollback(db: Session) -> None:
    expired = any(
        isinstance(row, AgentSession) and row.status == "expired"
        for row in db.dirty
    )
    if expired:
        db.commit()
    else:
        db.rollback()


def _default_failure(exc: Exception) -> tuple[TerminalStatus, str, dict[str, Any]]:
    if isinstance(exc, AgentSessionError):
        return "denied", exc.code, {}
    if isinstance(exc, AgentActionServiceError):
        return "denied", exc.code, {}
    return "failed", "domain_write_failed", {}


def _record_terminal(
    session_factory: SessionFactory,
    *,
    claim: ActionClaim,
    status: Literal["succeeded", "failed", "denied"],
    result: Mapping[str, Any] | Any,
    error_code: str | None,
) -> None:
    with session_factory() as audit_db:
        acquire_database_scan_write_lock_with_retry(audit_db)
        if status == "succeeded":
            complete_agent_action(audit_db, claim=claim, result=result)
        elif status == "denied":
            assert error_code is not None
            deny_agent_action(
                audit_db,
                claim=claim,
                error_code=error_code,
                result=result,
            )
        else:
            assert error_code is not None
            fail_agent_action(
                audit_db,
                claim=claim,
                error_code=error_code,
                result=result,
            )
        audit_db.commit()


def execute_audited_agent_action(
    session_factory: SessionFactory,
    *,
    session_id: UUID,
    raw_session_secret: str,
    tool_name: str,
    idempotency_key: str,
    request: Mapping[str, Any] | Any,
    mutation: Mutation,
    correlation_id: UUID | None = None,
    failure_mapper: FailureMapper | None = None,
) -> AgentActionExecution:
    """Execute one authorized write with a rollback-independent audit ledger.

    The reservation is committed before the domain transaction. The live session is
    authenticated and authorized again while the domain transaction owns the write
    lock. The mutation and success event commit atomically; failed or denied attempts
    are appended separately after rollback. A domain rollback therefore cannot erase
    the attempt, while a committed write is always replayable from its success event.
    """

    reserved_denial: ReservedAgentActionDenied | None = None
    with session_factory() as audit_db:
        try:
            # Reserve under one short database-level write transaction. The lock is
            # released before domain/provider I/O, so it elects deterministic owners
            # without starving the independent heartbeat connection.
            acquire_database_scan_write_lock_with_retry(audit_db)
            claim = _authorize_and_reserve_agent_action(
                audit_db,
                session_id=session_id,
                raw_session_secret=raw_session_secret,
                tool_name=tool_name,
                idempotency_key=idempotency_key,
                request=request,
                correlation_id=correlation_id,
            )
        except ReservedAgentActionDenied as exc:
            audit_db.commit()
            reserved_denial = exc
        except Exception:
            _commit_materialized_expiration_or_rollback(audit_db)
            raise
        else:
            audit_db.commit()

    if reserved_denial is not None:
        error = reserved_denial.error
        error_code = (
            error.code if isinstance(error, AgentSessionError) else "session_capability_error"
        )
        _record_terminal(
            session_factory,
            claim=reserved_denial.claim,
            status="denied",
            result={},
            error_code=error_code,
        )
        raise error

    if claim.outcome != "reserved":
        return AgentActionExecution(
            outcome=(
                "replay"
                if claim.outcome == "replay"
                else "in_progress"
                if claim.outcome == "in_progress"
                else "conflict"
            ),
            operation_id=claim.operation_id,
            correlation_id=claim.correlation_id,
            result=claim.replay_result,
            error_code=claim.replay_error_code or claim.error_code,
        )

    try:
        with session_factory() as domain_db:
            try:
                _authorize_agent_action_session(
                    domain_db,
                    session_id=session_id,
                    raw_session_secret=raw_session_secret,
                    tool_name=tool_name,
                    request=request,
                )
            except Exception:
                _commit_materialized_expiration_or_rollback(domain_db)
                raise
            try:
                result = mutation(domain_db)
                try:
                    complete_agent_action(domain_db, claim=claim, result=result)
                except InvalidActionTransition:
                    domain_db.rollback()
                    terminal = _core_terminal_event(domain_db, claim.operation_id)
                    if terminal is None or terminal.event_status != "succeeded":
                        raise
                    return AgentActionExecution(
                        outcome="replay",
                        operation_id=claim.operation_id,
                        correlation_id=claim.correlation_id,
                        result=summarize_result(
                            terminal.tool_name,
                            terminal.result_summary_json,
                        ),
                        error_code=IDEMPOTENCY_REPLAY,
                    )
                domain_db.commit()
            except Exception:
                domain_db.rollback()
                raise
    except Exception as exc:
        mapper = failure_mapper or _default_failure
        terminal_status, error_code, safe_result = mapper(exc)
        if terminal_status == "in_progress":
            return AgentActionExecution(
                outcome="in_progress",
                operation_id=claim.operation_id,
                correlation_id=claim.correlation_id,
                result=safe_result,
                error_code=error_code,
            )
        _record_terminal(
            session_factory,
            claim=claim,
            status=terminal_status,
            result=safe_result,
            error_code=error_code,
        )
        raise

    return AgentActionExecution(
        outcome="succeeded",
        operation_id=claim.operation_id,
        correlation_id=claim.correlation_id,
        result=result,
    )
