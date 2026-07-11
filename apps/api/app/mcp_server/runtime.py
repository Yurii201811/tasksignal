from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from secrets import token_urlsafe
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.version import TASKSIGNAL_VERSION
from app.models.all_models import AgentSession
from app.services.agent_sessions import (
    CONFIGURED_AI_CAPABILITY,
    STANDARD_WRITE_CAPABILITIES,
    AgentSessionError,
    SessionStateError,
    approve_session,
    hash_session_secret,
    heartbeat_session,
    mark_session_exited,
    register_session,
)


class MCPRuntimeStateError(RuntimeError):
    pass


def _locked_session(db: Session, session_id: UUID) -> AgentSession | None:
    return db.scalar(
        select(AgentSession)
        .where(AgentSession.id == session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _acquire_session_write_lock(db: Session) -> None:
    """Serialize a short session-row write without the scan advisory lock."""

    dialect = db.get_bind().dialect.name
    if dialect == "sqlite" and not db.in_transaction():
        # Keep heartbeat contention bounded so a retry can occur before the
        # two-missed-heartbeat lease expires.
        db.execute(text("PRAGMA busy_timeout = 2000"))
        db.commit()
        db.execute(text("BEGIN IMMEDIATE"))
    elif dialect == "postgresql" and not db.in_transaction():
        # SELECT FOR UPDATE must not consume the heartbeat loop indefinitely.
        db.execute(text("SET LOCAL lock_timeout = '2000ms'"))


@dataclass
class MCPProcessRuntime:
    """Own one process-bound agent session and its memory-only raw secret."""

    session_factory: Callable[[], Session]
    client_name: str = "TaskSignal MCP"
    client_version: str = TASKSIGNAL_VERSION
    heartbeat_interval_seconds: float = 30.0
    shutdown_timeout_seconds: float = 2.0
    process_instance_id: UUID = field(default_factory=uuid4)
    _session_id: UUID | None = field(default=None, init=False, repr=False)
    _raw_secret: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.heartbeat_interval_seconds <= 0:
            raise ValueError("The MCP heartbeat interval must be positive.")
        if self.shutdown_timeout_seconds <= 0:
            raise ValueError("The MCP shutdown timeout must be positive.")

    @property
    def session_id(self) -> UUID:
        if self._session_id is None:
            raise MCPRuntimeStateError("The MCP process session is not registered.")
        return self._session_id

    @property
    def raw_secret(self) -> str:
        if self._raw_secret is None:
            raise MCPRuntimeStateError("The MCP process secret is unavailable.")
        return self._raw_secret

    def register(self) -> UUID:
        if self._session_id is not None or self._raw_secret is not None:
            raise MCPRuntimeStateError("The MCP process session is already registered.")
        raw_secret = token_urlsafe(48)
        requested = set(STANDARD_WRITE_CAPABILITIES) | {CONFIGURED_AI_CAPABILITY}
        with self.session_factory() as db:
            _acquire_session_write_lock(db)
            session: AgentSession = register_session(
                db,
                secret_hash=hash_session_secret(raw_secret),
                client_name=self.client_name,
                client_version=self.client_version,
                process_instance_id=self.process_instance_id,
                transport="stdio",
                requested_capabilities=requested,
            )
            db.commit()
            session_id = session.id
        self._raw_secret = raw_secret
        self._session_id = session_id
        return session_id

    def approve_interactive(self, *, use_configured_ai: bool = False) -> None:
        """Apply an approval only after the caller has completed a real TTY prompt."""

        with self.session_factory() as db:
            _acquire_session_write_lock(db)
            session = _locked_session(db, self.session_id)
            if session is None:
                db.rollback()
                raise MCPRuntimeStateError("The MCP process session no longer exists.")
            try:
                approve_session(
                    session,
                    expected_version=session.version,
                    approval_source="interactive_tty",
                    include_configured_ai=use_configured_ai,
                )
            except AgentSessionError:
                if session.status == "expired":
                    db.commit()
                else:
                    db.rollback()
                raise
            db.commit()

    def heartbeat(self) -> bool:
        """Renew the process lease; return false after terminal session state."""

        with self.session_factory() as db:
            _acquire_session_write_lock(db)
            session = _locked_session(db, self.session_id)
            if session is None:
                db.rollback()
                return False
            try:
                heartbeat_session(session, raw_secret=self.raw_secret)
            except (SessionStateError, AgentSessionError):
                if session.status == "expired":
                    db.commit()
                else:
                    db.rollback()
                return False
            db.commit()
        return True

    def erase_secret(self) -> None:
        """Synchronously make the process credential unavailable."""

        self._raw_secret = None

    def close(self) -> None:
        """Mark an active process exited and erase the raw secret from runtime state."""

        # Secret erasure is synchronous and precedes any potentially blocking DB lock.
        self.erase_secret()
        if self._session_id is None:
            return
        with self.session_factory() as db:
            _acquire_session_write_lock(db)
            session = _locked_session(db, self._session_id)
            if session is not None and session.status in {"pending", "approved"}:
                try:
                    mark_session_exited(session, expected_version=session.version)
                except AgentSessionError:
                    if session.status == "expired":
                        db.commit()
                    else:
                        db.rollback()
                else:
                    db.commit()
            else:
                db.rollback()
