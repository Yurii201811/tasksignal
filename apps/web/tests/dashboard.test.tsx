import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Dashboard } from "../src/features/dashboard";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: {
    stats: vi.fn(),
    opportunities: vi.fn(),
    sources: vi.fn(),
    scans: vi.fn(),
    readiness: vi.fn(),
    processDemo: vi.fn(),
    createScan: vi.fn(),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.stats).mockResolvedValue({
      total_items: 0,
      problem_signals: 0,
      clusters: 0,
      opportunities: 0,
      source_breakdown: [],
      pain_distribution: [],
    });
    vi.mocked(api.opportunities).mockResolvedValue([]);
    vi.mocked(api.sources).mockResolvedValue([
      {
        id: "source-1",
        name: "Hacker News",
        type: "hackernews",
        config_json: {},
        enabled: true,
        created_at: "2026-06-03T10:00:00.000Z",
      },
    ]);
    vi.mocked(api.scans).mockResolvedValue([]);
    vi.mocked(api.readiness).mockResolvedValue({
      status: "ready",
      blockers: [],
      warnings: [
        "Create at least one saved research project.",
        "Run a project or process fixtures before exporting task packs.",
      ],
      checks: {
        projects: 0,
        opportunities: 0,
        due_projects: 0,
        local_workspace_configured: false,
        ready_sources: ["hackernews"],
        codex_task_packs: true,
        operator_scan_token_configured: false,
        public_scan_sources: ["fixture", "hackernews"],
      },
    });
  });

  it("renders the main processing action", () => {
    renderWithClient(<Dashboard />);
    expect(screen.getByText("Opportunity dashboard")).toBeInTheDocument();
    expect(screen.getByText("Process demo data")).toBeInTheDocument();
    expect(screen.getByText("Live source")).toBeInTheDocument();
    expect(screen.getByText("Run scan")).toBeInTheDocument();
  });

  it("renders readiness-driven first-use steps", async () => {
    renderWithClient(<Dashboard />);

    expect(await screen.findByText("First useful run")).toBeInTheDocument();
    expect(screen.getByText("Set workspace defaults")).toBeInTheDocument();
    expect(screen.getByText("Save a research project")).toBeInTheDocument();
    expect(screen.getByText("Generate ranked opportunities")).toBeInTheDocument();
    expect(screen.getByText("Export a task pack")).toBeInTheDocument();
    expect(
      await screen.findByText("Create at least one saved research project."),
    ).toBeInTheDocument();
  });
});
