from __future__ import annotations

import asyncio
from threading import Event
from time import monotonic, sleep

import anyio
import pytest

from app.db.session import SessionLocal
from app.mcp_server.lifecycle import process_lifespan
from app.mcp_server.runtime import MCPProcessRuntime, MCPRuntimeStateError
from app.models.all_models import AgentSession


def test_lifespan_registers_heartbeats_and_exits_without_secret_leak(client) -> None:
    del client
    runtime = MCPProcessRuntime(SessionLocal, heartbeat_interval_seconds=0.01)

    async def exercise() -> tuple[object, int]:
        lifespan = process_lifespan(
            runtime,
            approval_callback=lambda state: state.approve_interactive(),
        )
        async with lifespan(None) as state:
            assert state is runtime
            with SessionLocal() as db:
                initial = db.get(AgentSession, runtime.session_id)
                assert initial is not None
                initial_version = initial.version
                assert initial.status == "approved"
            await anyio.sleep(0.04)
            with SessionLocal() as db:
                renewed = db.get(AgentSession, runtime.session_id)
                assert renewed is not None
                return renewed.status, renewed.version - initial_version

    active_status, heartbeat_count = asyncio.run(exercise())

    assert active_status == "approved"
    assert heartbeat_count >= 1
    with SessionLocal() as db:
        exited = db.get(AgentSession, runtime.session_id)
        assert exited is not None
        assert exited.status == "exited"
    with pytest.raises(MCPRuntimeStateError, match="secret is unavailable"):
        _ = runtime.raw_secret


def test_runtime_rejects_nonpositive_heartbeat_interval() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        MCPProcessRuntime(SessionLocal, heartbeat_interval_seconds=0)


def test_heartbeat_runs_while_interactive_approval_waits(client) -> None:
    del client
    runtime = MCPProcessRuntime(SessionLocal, heartbeat_interval_seconds=0.01)

    def delayed_approval(state: MCPProcessRuntime) -> None:
        sleep(0.06)
        state.approve_interactive()

    async def exercise() -> int:
        lifespan = process_lifespan(runtime, approval_callback=delayed_approval)
        async with lifespan(None):
            with SessionLocal() as db:
                row = db.get(AgentSession, runtime.session_id)
                assert row is not None
                assert row.status == "approved"
                return row.version

    version_after_approval = asyncio.run(exercise())

    # Registration is v1; at least one pending heartbeat and approval both advance it.
    assert version_after_approval >= 3


def test_blocked_workers_do_not_defeat_bounded_shutdown(client, monkeypatch) -> None:
    del client
    runtime = MCPProcessRuntime(
        SessionLocal,
        heartbeat_interval_seconds=0.01,
        shutdown_timeout_seconds=0.05,
    )

    def blocked_heartbeat() -> bool:
        sleep(0.3)
        return True

    def blocked_close() -> None:
        runtime._raw_secret = None
        sleep(0.3)

    monkeypatch.setattr(runtime, "heartbeat", blocked_heartbeat)
    monkeypatch.setattr(runtime, "close", blocked_close)

    async def exercise() -> None:
        lifespan = process_lifespan(runtime)
        async with lifespan(None):
            await anyio.sleep(0.03)

    started = monotonic()
    asyncio.run(exercise())
    elapsed = monotonic() - started

    assert elapsed < 0.2
    with pytest.raises(MCPRuntimeStateError, match="secret is unavailable"):
        _ = runtime.raw_secret


def test_default_worker_pool_saturation_cannot_skip_cleanup(client) -> None:
    del client
    runtime = MCPProcessRuntime(
        SessionLocal,
        heartbeat_interval_seconds=1,
        shutdown_timeout_seconds=0.1,
    )
    worker_started = Event()
    release_worker = Event()

    def occupy_default_worker() -> None:
        worker_started.set()
        assert release_worker.wait(timeout=2)

    async def exercise() -> None:
        default_limiter = anyio.to_thread.current_default_thread_limiter()
        original_tokens = default_limiter.total_tokens
        default_limiter.total_tokens = 1
        try:
            lifespan = process_lifespan(runtime)
            async with anyio.create_task_group() as tasks:
                async with lifespan(None):
                    tasks.start_soon(
                        anyio.to_thread.run_sync,
                        occupy_default_worker,
                    )
                    while not worker_started.is_set():
                        await anyio.sleep(0.001)
                with pytest.raises(MCPRuntimeStateError, match="secret is unavailable"):
                    _ = runtime.raw_secret
                with SessionLocal() as db:
                    row = db.get(AgentSession, runtime.session_id)
                    assert row is not None
                    assert row.status == "exited"
                release_worker.set()
        finally:
            release_worker.set()
            default_limiter.total_tokens = original_tokens

    asyncio.run(exercise())
