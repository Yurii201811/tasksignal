import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentSessions } from "../src/features/agent-sessions";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: {
    agentSessions: vi.fn(),
    approveAgentSession: vi.fn(),
    revokeAgentSession: vi.fn(),
    agentSessionActions: vi.fn(),
  },
}));

const pendingSession = {
  id: "session-1",
  process_instance_id: "process-1",
  client_name: "Codex MCP",
  client_version: "1.0",
  transport: "stdio" as const,
  status: "pending" as const,
  effective_status: "pending" as const,
  requested_capabilities: [
    "create_project",
    "update_project",
    "run_project",
    "set_opportunity_decision",
    "append_evidence_label",
    "create_build_packet",
    "use_configured_ai",
  ],
  approved_capabilities: [],
  approval_source: null,
  approved_at: null,
  last_heartbeat_at: "2026-07-11T10:00:00Z",
  expires_at: "2026-07-11T10:01:00Z",
  revoked_at: null,
  expired_at: null,
  exited_at: null,
  version: 2,
  created_at: "2026-07-11T10:00:00Z",
  updated_at: "2026-07-11T10:00:00Z",
};

function renderFeature() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AgentSessions />
    </QueryClientProvider>,
  );
}

describe("AgentSessions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.agentSessions).mockResolvedValue([pendingSession]);
    vi.mocked(api.approveAgentSession).mockResolvedValue({
      ...pendingSession,
      status: "approved",
      effective_status: "approved",
      version: 3,
      approval_source: "ui",
      approved_capabilities: pendingSession.requested_capabilities,
      approved_at: "2026-07-11T10:00:10Z",
    });
    vi.mocked(api.agentSessionActions).mockResolvedValue([
      {
        id: "action-1",
        session_id: "session-1",
        operation_id: "operation-1",
        correlation_id: "correlation-1",
        event_sequence: 2,
        event_status: "succeeded",
        capability: "create_build_packet",
        tool_name: "create_build_packet",
        target_type: "thread",
        target_id: "thread-1",
        request_summary: {
          generation_mode: "deterministic",
          secret: "[redacted]",
        },
        result_summary: { packet_id: "packet-1" },
        error_code: null,
        created_at: "2026-07-11T10:00:20Z",
      },
    ]);
  });

  it("approves a process-bound session and shows the redacted audit", async () => {
    renderFeature();

    expect(await screen.findByText("Codex MCP")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: /configured AI/i }));
    fireEvent.click(screen.getByRole("button", { name: "Approve session" }));
    await waitFor(() =>
      expect(api.approveAgentSession).toHaveBeenCalledWith(
        "session-1",
        2,
        true,
      ),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "View redacted audit" }),
    );
    expect(await screen.findByText("create_build_packet")).toBeInTheDocument();
    expect(screen.getByText(/\[redacted\]/)).toBeInTheDocument();
    expect(
      screen.getByText(/summaries are redacted by the API/i),
    ).toBeInTheDocument();
  });

  it("shows only capabilities actually granted to an approved session", async () => {
    vi.mocked(api.agentSessions).mockResolvedValue([
      {
        ...pendingSession,
        status: "approved",
        effective_status: "approved",
        approved_capabilities: pendingSession.requested_capabilities.filter(
          (capability) => capability !== "use_configured_ai",
        ),
        approval_source: "ui",
        approved_at: "2026-07-11T10:00:10Z",
      },
    ]);

    renderFeature();

    expect(
      await screen.findByText("Approved capabilities"),
    ).toBeInTheDocument();
    expect(screen.queryByText("use configured ai")).not.toBeInTheDocument();
    expect(screen.getByText("create build packet")).toBeInTheDocument();
  });

  it("hides unrequested configured AI while allowing standard approval", async () => {
    const standardSession = {
      ...pendingSession,
      requested_capabilities: pendingSession.requested_capabilities.filter(
        (capability) => capability !== "use_configured_ai",
      ),
    };
    vi.mocked(api.agentSessions).mockResolvedValue([standardSession]);
    vi.mocked(api.approveAgentSession).mockResolvedValue({
      ...standardSession,
      status: "approved",
      effective_status: "approved",
      version: 3,
      approval_source: "ui",
      approved_capabilities: standardSession.requested_capabilities,
      approved_at: "2026-07-11T10:00:10Z",
    });

    renderFeature();

    expect(await screen.findByText("Codex MCP")).toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: /configured AI/i }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve session" }));
    await waitFor(() =>
      expect(api.approveAgentSession).toHaveBeenCalledWith(
        "session-1",
        2,
        false,
      ),
    );
  });

  it("refreshes the optimistic version after an approval conflict", async () => {
    const refreshed = { ...pendingSession, version: 3 };
    vi.mocked(api.agentSessions)
      .mockResolvedValueOnce([pendingSession])
      .mockResolvedValue([refreshed]);
    vi.mocked(api.approveAgentSession)
      .mockRejectedValueOnce(new Error('{"detail":"version conflict"}'))
      .mockResolvedValue({
        ...refreshed,
        status: "approved",
        effective_status: "approved",
        version: 4,
        approval_source: "ui",
        approved_capabilities: refreshed.requested_capabilities.filter(
          (capability) => capability !== "use_configured_ai",
        ),
        approved_at: "2026-07-11T10:00:20Z",
      });
    renderFeature();

    fireEvent.click(
      await screen.findByRole("button", { name: "Approve session" }),
    );
    await waitFor(() => expect(api.agentSessions).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "Approve session" }));

    await waitFor(() =>
      expect(api.approveAgentSession).toHaveBeenLastCalledWith(
        "session-1",
        3,
        false,
      ),
    );
  });

  it("polls often enough to keep the heartbeat lease current", async () => {
    vi.useFakeTimers();
    try {
      renderFeature();
      await act(async () => {
        await Promise.resolve();
      });
      expect(api.agentSessions).toHaveBeenCalledTimes(1);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(15_000);
      });

      expect(api.agentSessions).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
