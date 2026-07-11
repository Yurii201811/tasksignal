from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from typing import Any

import anyio

from app.mcp_server.runtime import MCPProcessRuntime

LOGGER = logging.getLogger(__name__)
ApprovalCallback = Callable[[MCPProcessRuntime], None]


async def _heartbeat_loop(
    runtime: MCPProcessRuntime,
    worker_limiter: anyio.CapacityLimiter,
) -> None:
    delay = runtime.heartbeat_interval_seconds
    while True:
        await anyio.sleep(delay)
        try:
            active = await anyio.to_thread.run_sync(
                runtime.heartbeat,
                abandon_on_cancel=True,
                limiter=worker_limiter,
            )
        except Exception:  # pragma: no cover - defensive runtime resilience
            LOGGER.exception("TaskSignal MCP heartbeat failed; the lease may expire.")
            delay = min(5.0, runtime.heartbeat_interval_seconds)
            continue
        if not active:
            return
        delay = runtime.heartbeat_interval_seconds


def process_lifespan(
    runtime: MCPProcessRuntime,
    *,
    approval_callback: ApprovalCallback | None = None,
) -> Callable[[Any], Any]:
    """Create a FastMCP-compatible lifespan around one process runtime."""

    @asynccontextmanager
    async def lifespan(_server: Any) -> AsyncIterator[MCPProcessRuntime]:
        # Approval may wait on a TTY while heartbeat and shutdown must still run.
        # A private limiter also prevents unrelated default-pool saturation from
        # delaying lease maintenance or secret erasure.
        worker_limiter = anyio.CapacityLimiter(2)
        await anyio.to_thread.run_sync(runtime.register, limiter=worker_limiter)
        try:
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(_heartbeat_loop, runtime, worker_limiter)
                try:
                    if approval_callback is not None:
                        await anyio.to_thread.run_sync(
                            partial(approval_callback, runtime),
                            abandon_on_cancel=True,
                            limiter=worker_limiter,
                        )
                    yield runtime
                finally:
                    tasks.cancel_scope.cancel()
        finally:
            # Never put in-memory credential erasure behind a worker token or DB lock.
            runtime.erase_secret()
            with anyio.CancelScope(shield=True):
                with anyio.move_on_after(runtime.shutdown_timeout_seconds):
                    await anyio.to_thread.run_sync(
                        runtime.close,
                        abandon_on_cancel=True,
                        limiter=worker_limiter,
                    )

    return lifespan
