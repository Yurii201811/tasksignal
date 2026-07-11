from __future__ import annotations

import asyncio

from app.mcp_server.server import create_mcp_server

READ_TOOLS = {
    "list_projects",
    "list_project_runs",
    "compare_project_runs",
    "search_opportunities",
    "get_opportunity_thread",
    "get_evaluation",
    "get_build_packet",
    "verify_build_packet",
}
WRITE_TOOLS = {
    "create_project",
    "update_project",
    "run_project",
    "set_opportunity_decision",
    "append_evidence_label",
    "create_build_packet",
}


def test_server_exposes_exact_typed_allowlist_and_safe_annotations() -> None:
    server = create_mcp_server()
    tools = asyncio.run(server.list_tools())
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == READ_TOOLS | WRITE_TOOLS
    assert not (
        set(by_name)
        & {
            "delete_project",
            "reset_data",
            "authorize_source",
            "set_credentials",
            "fetch_url",
            "run_shell",
            "write_file",
            "create_github_issue",
        }
    )
    for name in READ_TOOLS:
        annotations = by_name[name].annotations
        assert annotations is not None
        assert annotations.readOnlyHint is True
        assert annotations.destructiveHint is False
        assert annotations.openWorldHint is False
        assert by_name[name].outputSchema is not None
    for name in WRITE_TOOLS:
        tool = by_name[name]
        annotations = tool.annotations
        assert annotations is not None
        assert annotations.readOnlyHint is False
        assert annotations.destructiveHint is False
        assert annotations.idempotentHint is True
        assert "idempotency_key" in tool.inputSchema["properties"]
        assert "expected_version" in tool.inputSchema["properties"]
        assert "idempotency_key" in tool.inputSchema["required"]
        assert "expected_version" in tool.inputSchema["required"]
        assert "raw_session_secret" not in tool.inputSchema["properties"]
        assert tool.outputSchema is not None
    assert by_name["run_project"].annotations.openWorldHint is True
    assert by_name["create_build_packet"].annotations.openWorldHint is True


def test_server_exposes_exact_resource_templates() -> None:
    templates = asyncio.run(create_mcp_server().list_resource_templates())

    assert [template.uriTemplate for template in templates] == [
        "tasksignal://projects/{project_id}/runs/{run_id}/delta",
        "tasksignal://opportunity-threads/{thread_id}",
        "tasksignal://build-packets/{packet_id}/artifacts/{artifact_name}",
    ]
    assert [template.mimeType for template in templates] == [
        "application/json",
        "application/json",
        "text/plain; charset=utf-8",
    ]
