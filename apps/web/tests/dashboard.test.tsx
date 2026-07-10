import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Dashboard } from "../src/features/dashboard";
import { api } from "../src/lib/api";
import type { Opportunity, ReviewState } from "../src/lib/types";

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

const readiness = {
  level: "medium" as const,
  evidence_count: 5,
  source_count: 2,
  safe_url_count: 4,
  reviewed_count: 2,
  source_url_coverage: 0.8,
  human_review_coverage: 0.4,
  checks: {
    enough_evidence: true,
    source_diversity: true,
    source_url_coverage: true,
    human_review_coverage: false,
  },
  passed_checks: [
    "enough_evidence" as const,
    "source_diversity" as const,
    "source_url_coverage" as const,
  ],
  gaps: ["Review 1 more evidence item."],
};

function opportunity(id: string, title: string, reviewState: ReviewState): Opportunity {
  return {
    id,
    cluster_id: `cluster-${id}`,
    title,
    problem_statement: "Repeated workflow pain.",
    target_user: "Maintainers",
    current_workaround: "Manual work",
    suggested_mvp: "Focused local tool",
    why_now: "Repeated evidence",
    feasibility_score: 0.8,
    opportunity_score: 0.7,
    competition_notes: "Narrow scope",
    scoring_breakdown_json: {},
    generated_prompt: "# Build",
    review_state: reviewState,
    review_note: null,
    decision_updated_at: null,
    evidence_readiness: readiness,
    created_at: "2026-07-09T10:00:00Z",
    updated_at: "2026-07-09T10:00:00Z",
    evidence_items: [],
    signal_count: 5,
    top_source: "github",
  };
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
    expect(screen.getByText(/Examples: ask, show, job/)).toBeInTheDocument();
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

  it("filters the decision queue locally without another API call", async () => {
    vi.mocked(api.opportunities).mockResolvedValue([
      opportunity("1", "New idea", "new"),
      opportunity("2", "Promising idea", "promising"),
      opportunity("3", "Rejected idea", "rejected"),
    ]);
    renderWithClient(<Dashboard />);

    expect(await screen.findByText("Promising idea")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Promising 1" }));

    expect(screen.getByText("Promising idea")).toBeInTheDocument();
    expect(screen.queryByText("New idea")).not.toBeInTheDocument();
    expect(screen.queryByText("Rejected idea")).not.toBeInTheDocument();
    expect(api.opportunities).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Promising")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Build candidate 0" }));
    expect(screen.getByText("No opportunities match this decision state")).toBeInTheDocument();
    expect(screen.queryByText("No ranked opportunities yet")).not.toBeInTheDocument();
  });
});
