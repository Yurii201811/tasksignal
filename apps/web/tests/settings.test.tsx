import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "../src/app/settings/page";
import { api } from "../src/lib/api";
import type { Integration, LocalWorkspace, Readiness } from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  api: {
    integrations: vi.fn(),
    localWorkspace: vi.fn(),
    readiness: vi.fn(),
    updateLocalWorkspace: vi.fn(),
    testIntegration: vi.fn(),
  },
}));

const workspace: LocalWorkspace = {
  id: 1,
  owner_name: "Local operator",
  workspace_goal: "Developer-tool ideas",
  default_source_type: "hackernews",
  default_query: "ask",
  default_limit: 30,
  default_cadence: "manual",
  default_schedule_interval_hours: null,
  configured: true,
  created_at: "2026-09-01T09:00:00Z",
  updated_at: "2026-09-01T09:00:00Z",
};

const readiness: Readiness = {
  status: "ready",
  blockers: [],
  warnings: [],
  checks: {
    projects: 1,
    opportunities: 5,
    build_packets: 0,
    due_projects: 0,
    local_workspace_configured: true,
    codex_task_packs: true,
  },
};

const hackerNews: Integration = {
  id: "hackernews",
  name: "Hacker News",
  kind: "public_source",
  status: "ready",
  credential_state: "not_required",
  public_scan_enabled: true,
  operator_token_required: false,
  required_env: [],
  optional_env: [],
  rate_limit_note: "Public API rate limits apply.",
  privacy_note: "Stores public story fields only.",
  next_step: "Run a public scan.",
  last_scan_status: null,
  last_scan_at: null,
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(api.localWorkspace).mockResolvedValue(workspace);
    vi.mocked(api.readiness).mockResolvedValue(readiness);
    vi.mocked(api.integrations).mockResolvedValue([hackerNews]);
  });

  it("retries a failed integrations load instead of silently showing nothing", async () => {
    vi.mocked(api.integrations)
      .mockRejectedValueOnce(
        new Error('{"detail":"Connector registry unavailable"}'),
      )
      .mockResolvedValue([hackerNews]);

    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load integrations");
    expect(alert).toHaveTextContent("Connector registry unavailable");

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", { name: "Hacker News", level: 2 }),
    ).toBeInTheDocument();
    await waitFor(() => expect(api.integrations).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps workspace saving disabled until the stored profile has loaded", async () => {
    vi.mocked(api.localWorkspace).mockRejectedValue(
      new Error('{"detail":"Profile store unavailable"}'),
    );

    renderPage();

    expect(
      await screen.findByText("Could not load the local workspace profile"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Profile store unavailable/)).toBeInTheDocument();
    expect(screen.getByText("Local profile unavailable")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save workspace" }),
    ).toBeDisabled();
  });

  it("loads the stored profile into the form and surfaces readiness failures with Retry", async () => {
    vi.mocked(api.readiness)
      .mockRejectedValueOnce(new Error('{"detail":"Readiness probe failed"}'))
      .mockResolvedValue(readiness);

    renderPage();

    expect(
      await screen.findByDisplayValue("Local operator"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save workspace" }),
    ).toBeEnabled();
    expect(screen.getByText("Local user set")).toBeInTheDocument();

    expect(
      await screen.findByText("Readiness check failed"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Readiness probe failed/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", { name: "Workspace readiness" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Readiness check failed"),
    ).not.toBeInTheDocument();
  });
});
