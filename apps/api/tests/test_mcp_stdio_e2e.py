from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.all_models import AgentSession
from app.services.agent_sessions import approve_session

API_ROOT = Path(__file__).resolve().parents[1]


def _subprocess_database_url() -> str:
    database_url = os.environ["DATABASE_URL"]
    sqlite_prefix = "sqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return database_url
    database_path = Path(database_url.removeprefix(sqlite_prefix)).expanduser()
    if database_path.is_absolute():
        return database_url
    return f"{sqlite_prefix}{(Path.cwd() / database_path).resolve()}"


def test_real_stdio_server_reads_approval_write_replay_and_cleanup(client, tmp_path) -> None:
    processed = client.post("/api/v1/process/demo")
    assert processed.status_code == 200
    thread = client.get("/api/v1/opportunity-threads").json()[0]
    stderr_path = tmp_path / "mcp-stderr.log"

    async def exercise() -> tuple[dict, dict, UUID]:
        environment = dict(os.environ)
        environment["PYTHONUNBUFFERED"] = "1"
        # SQLite URLs are relative to each process's working directory. The MCP
        # subprocess starts in apps/api, so pass the parent's canonical database
        # path to exercise one real shared session instead of a stale second file.
        environment["DATABASE_URL"] = _subprocess_database_url()
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server.server"],
            cwd=API_ROOT,
            env=environment,
        )
        with stderr_path.open("w+", encoding="utf-8") as errlog:
            async with stdio_client(parameters, errlog=errlog) as streams:
                async with ClientSession(
                    *streams,
                    read_timeout_seconds=timedelta(seconds=10),
                ) as mcp_client:
                    await mcp_client.initialize()
                    tools = await mcp_client.list_tools()
                    assert len(tools.tools) == 14
                    templates = await mcp_client.list_resource_templates()
                    assert len(templates.resourceTemplates) == 3

                    evaluation = await mcp_client.call_tool("get_evaluation", {})
                    assert evaluation.isError is False
                    assert evaluation.structuredContent is not None
                    assert evaluation.structuredContent["total_reviewable_items"] >= 1

                    denied = await mcp_client.call_tool(
                        "create_project",
                        {
                            "idempotency_key": "stdio-project-denied-0001",
                            "expected_version": 1,
                            "name": "Denied before approval",
                            "source_type": "fixture",
                        },
                    )
                    assert denied.structuredContent is not None
                    assert denied.structuredContent["ok"] is False
                    assert denied.structuredContent["error"]["code"] == (
                        "session_state_error"
                    )

                    with SessionLocal() as db:
                        session = db.scalar(
                            select(AgentSession).order_by(AgentSession.created_at.desc())
                        )
                        assert session is not None
                        session_id = session.id
                        approve_session(
                            session,
                            expected_version=session.version,
                            approval_source="ui",
                        )
                        db.commit()

                    arguments = {
                        "idempotency_key": "stdio-project-approved-0001",
                        "expected_version": 1,
                        "name": "Approved stdio project",
                        "source_type": "fixture",
                        "query": "workflow",
                    }
                    created = await mcp_client.call_tool("create_project", arguments)
                    replay = await mcp_client.call_tool("create_project", arguments)
                    assert created.structuredContent is not None
                    assert replay.structuredContent is not None
                    assert created.structuredContent["outcome"] == "succeeded"
                    assert replay.structuredContent["outcome"] == "replay"
                    assert replay.structuredContent["result"] == created.structuredContent["result"]

                    resource = await mcp_client.read_resource(
                        AnyUrl(f"tasksignal://opportunity-threads/{thread['id']}")
                    )
                    assert resource.contents
                    resource_text = resource.contents[0].text
                    assert thread["id"] in resource_text
                    assert "review_note" not in resource_text
                    return (
                        created.structuredContent,
                        replay.structuredContent,
                        session_id,
                    )

    created, replay, session_id = asyncio.run(exercise())

    assert created["result"] == replay["result"]
    with SessionLocal() as db:
        session = db.get(AgentSession, session_id)
        assert session is not None
        assert session.status == "exited"
    stderr = stderr_path.read_text(encoding="utf-8")
    assert "secret_hash" not in stderr
    assert "raw_session_secret" not in stderr
    assert "Traceback" not in stderr
