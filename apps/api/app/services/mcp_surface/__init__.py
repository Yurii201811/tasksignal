"""SDK-independent MCP domain surfaces.

The MCP transport adapts these plain Python functions and dictionaries to the
SDK. Keeping database reads here prevents protocol concerns from leaking into
the research, review, and build-packet services.
"""

from app.services.mcp_surface.reads import (
    McpReadError,
    compare_project_runs,
    get_build_packet,
    get_evaluation,
    get_opportunity_thread,
    list_project_runs,
    list_projects,
    list_resource_templates,
    list_resources,
    resolve_resource,
    search_opportunities,
    verify_build_packet,
)

__all__ = [
    "McpReadError",
    "compare_project_runs",
    "get_build_packet",
    "get_evaluation",
    "get_opportunity_thread",
    "list_project_runs",
    "list_projects",
    "list_resource_templates",
    "list_resources",
    "resolve_resource",
    "search_opportunities",
    "verify_build_packet",
]
