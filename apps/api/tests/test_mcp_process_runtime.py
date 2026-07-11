from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest

from app.db.session import SessionLocal
from app.mcp_server.runtime import (
    MCPProcessRuntime,
    MCPRuntimeStateError,
    _acquire_session_write_lock,
)
from app.models.all_models import AgentSession
from app.services.agent_sessions import (
    CONFIGURED_AI_CAPABILITY,
    STANDARD_WRITE_CAPABILITIES,
    SessionStateError,
)
from app.workers.scan_pipeline import SCAN_WRITE_LOCK


def test_runtime_registers_pending_session_without_persisting_raw_secret(client) -> None:
    del client
    runtime = MCPProcessRuntime(SessionLocal)

    session_id = runtime.register()

    assert runtime.session_id == session_id
    assert runtime.raw_secret not in repr(runtime)
    with SessionLocal() as db:
        row = db.get(AgentSession, session_id)
        assert row is not None
        assert row.status == "pending"
        assert set(row.requested_capabilities_json) == (
            set(STANDARD_WRITE_CAPABILITIES) | {CONFIGURED_AI_CAPABILITY}
        )
        assert row.approved_capabilities_json == []
        assert runtime.raw_secret != row.secret_hash
        assert len(row.secret_hash) == 64


def test_runtime_tty_approval_heartbeat_and_clean_exit(client) -> None:
    del client
    runtime = MCPProcessRuntime(SessionLocal)
    session_id = runtime.register()
    runtime.approve_interactive(use_configured_ai=True)

    with SessionLocal() as db:
        approved = db.get(AgentSession, session_id)
        assert approved is not None
        approved_version = approved.version
        assert approved.status == "approved"
        assert approved.approval_source == "interactive_tty"
        assert CONFIGURED_AI_CAPABILITY in approved.approved_capabilities_json

    assert runtime.heartbeat() is True
    with SessionLocal() as db:
        renewed = db.get(AgentSession, session_id)
        assert renewed is not None
        assert renewed.version == approved_version + 1

    runtime.close()
    with SessionLocal() as db:
        exited = db.get(AgentSession, session_id)
        assert exited is not None
        assert exited.status == "exited"
    with pytest.raises(MCPRuntimeStateError, match="secret is unavailable"):
        _ = runtime.raw_secret


def test_runtime_stops_heartbeat_after_operator_revocation(client) -> None:
    del client
    runtime = MCPProcessRuntime(SessionLocal)
    session_id = runtime.register()
    runtime.approve_interactive()
    with SessionLocal() as db:
        row = db.get(AgentSession, session_id)
        assert row is not None
        row.status = "revoked"
        row.revoked_at = row.updated_at
        db.commit()

    assert runtime.heartbeat() is False
    runtime.close()
    with SessionLocal() as db:
        row = db.get(AgentSession, session_id)
        assert row is not None
        assert row.status == "revoked"


def test_runtime_rejects_duplicate_registration(client) -> None:
    del client
    runtime = MCPProcessRuntime(SessionLocal)
    runtime.register()
    try:
        runtime.register()
    except MCPRuntimeStateError as exc:
        assert "already registered" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Duplicate MCP runtime registration was accepted.")
    runtime.close()


def test_close_persists_expiration_discovered_at_shutdown(client) -> None:
    del client
    runtime = MCPProcessRuntime(SessionLocal)
    session_id = runtime.register()
    with SessionLocal() as db:
        row = db.get(AgentSession, session_id)
        assert row is not None
        row.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=2)
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    runtime.close()

    with SessionLocal() as db:
        row = db.get(AgentSession, session_id)
        assert row is not None
        assert row.status == "expired"
        assert row.expired_at is not None


def test_interactive_approval_persists_expiration_discovered_during_approval(client) -> None:
    del client
    runtime = MCPProcessRuntime(SessionLocal)
    session_id = runtime.register()
    with SessionLocal() as db:
        row = db.get(AgentSession, session_id)
        assert row is not None
        row.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=2)
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    with pytest.raises(SessionStateError, match="expired"):
        runtime.approve_interactive()

    with SessionLocal() as db:
        row = db.get(AgentSession, session_id)
        assert row is not None
        assert row.status == "expired"
        assert row.expired_at is not None


def test_postgresql_session_lock_uses_bounded_lock_timeout() -> None:
    class PostgreSQLBind:
        class Dialect:
            name = "postgresql"

        dialect = Dialect()

    statements: list[str] = []

    class PostgreSQLSession:
        def get_bind(self) -> PostgreSQLBind:
            return PostgreSQLBind()

        def in_transaction(self) -> bool:
            return False

        def execute(self, statement) -> None:
            statements.append(str(statement))

    _acquire_session_write_lock(PostgreSQLSession())  # type: ignore[arg-type]

    assert statements == ["SET LOCAL lock_timeout = '2000ms'"]


def test_heartbeat_does_not_wait_for_global_scan_process_lock(client) -> None:
    del client
    runtime = MCPProcessRuntime(SessionLocal)
    runtime.register()
    lock_held = Event()
    release_lock = Event()

    def hold_global_lock() -> None:
        with SCAN_WRITE_LOCK:
            lock_held.set()
            assert release_lock.wait(timeout=2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(hold_global_lock)
        assert lock_held.wait(timeout=2)
        heartbeat = pool.submit(runtime.heartbeat)
        heartbeat_finished_without_scan_lock = heartbeat.done() or heartbeat.result(timeout=1)
        release_lock.set()
        holder.result(timeout=2)

    assert heartbeat_finished_without_scan_lock is True
    runtime.close()
