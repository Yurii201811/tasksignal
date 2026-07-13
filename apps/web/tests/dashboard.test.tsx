import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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
    researchProjects: vi.fn(),
    processDemo: vi.fn(),
    createScan: vi.fn(),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    client,
    ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>),
  };
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

function opportunity(
  id: string,
  title: string,
  reviewState: ReviewState,
): Opportunity {
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
    vi.mocked(api.researchProjects).mockResolvedValue([
      {
        id: "project-1",
        name: "CI research",
        description: null,
        source_type: "github",
        query: "ci pain",
        limit: 30,
        cadence: "manual",
        schedule_interval_hours: null,
        labels: [],
        enabled: true,
        last_scan_id: null,
        last_scan_status: null,
        last_run_at: null,
        next_run_at: null,
        run_count: 1,
        created_at: "2026-07-09T10:00:00Z",
        updated_at: "2026-07-09T10:00:00Z",
      },
    ]);
  });

  it("renders the main processing action", async () => {
    renderWithClient(<Dashboard />);
    expect(screen.getByText("Opportunity dashboard")).toBeInTheDocument();
    expect(screen.getByText("Process demo data")).toBeInTheDocument();
    expect(screen.getByText("Live source")).toBeInTheDocument();
    expect(screen.getByText("Run scan")).toBeInTheDocument();
    expect(screen.getByText(/Examples: ask, show, job/)).toBeInTheDocument();
    expect(screen.getByText("Opportunity snapshots")).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: "No new items" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Raw public-source items available locally").tagName,
    ).toBe("DD");
  });

  it("renders one live source option when the API repeats a source type", async () => {
    vi.mocked(api.sources).mockResolvedValue([
      {
        id: "source-1",
        name: "Hacker News",
        type: "hackernews",
        config_json: {},
        enabled: true,
        created_at: "2026-06-03T10:00:00.000Z",
      },
      {
        id: "source-2",
        name: "Hacker News",
        type: "hackernews",
        config_json: {},
        enabled: true,
        created_at: "2026-07-10T10:00:00.000Z",
      },
    ]);

    const { client } = renderWithClient(<Dashboard />);
    await waitFor(() => expect(client.isFetching()).toBe(0));

    const liveSource = screen.getByRole("combobox", { name: "Live source" });
    expect(
      within(liveSource).getAllByRole("option", { name: "Hacker News" }),
    ).toHaveLength(1);
  });

  it("renders readiness-driven first-use steps", async () => {
    renderWithClient(<Dashboard />);

    expect(await screen.findByText("First useful run")).toBeInTheDocument();
    expect(screen.getByText("Set workspace defaults")).toBeInTheDocument();
    expect(screen.getByText("Save a research project")).toBeInTheDocument();
    expect(
      screen.getByText("Generate ranked opportunities"),
    ).toBeInTheDocument();
    expect(screen.getByText("Export a task pack")).toBeInTheDocument();
    expect(
      await screen.findByText("Create at least one saved research project."),
    ).toBeInTheDocument();
  });

  it("filters the decision queue through the API", async () => {
    const rows = [
      opportunity("1", "New idea", "new"),
      opportunity("2", "Promising idea", "promising"),
      opportunity("3", "Rejected idea", "rejected"),
    ];
    vi.mocked(api.opportunities).mockImplementation(async (filters) =>
      filters?.reviewState
        ? rows.filter((item) => item.review_state === filters.reviewState)
        : rows,
    );
    renderWithClient(<Dashboard />);

    expect(await screen.findByText("Promising idea")).toBeInTheDocument();
    expect(api.opportunities).toHaveBeenCalledWith({ currentOnly: true });
    expect(
      screen.getByRole("group", { name: "Decision state filter" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Promising 1" }));

    await waitFor(() =>
      expect(api.opportunities).toHaveBeenLastCalledWith({
        currentOnly: true,
        reviewState: "promising",
      }),
    );
    expect(await screen.findByText("Promising idea")).toBeInTheDocument();
    expect(screen.queryByText("New idea")).not.toBeInTheDocument();
    expect(screen.queryByText("Rejected idea")).not.toBeInTheDocument();
    expect(api.opportunities).toHaveBeenCalledTimes(2);
    expect(screen.getByText("Promising")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
    expect(
      screen.getByRole("meter", {
        name: "Promising idea feasibility score",
      }),
    ).toHaveAttribute("aria-valuetext", "80 percent");
    expect(
      screen.getByRole("region", { name: "Top opportunities" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Build candidate 0" }));
    await waitFor(() =>
      expect(api.opportunities).toHaveBeenLastCalledWith({
        currentOnly: true,
        reviewState: "build_candidate",
      }),
    );
    expect(
      await screen.findByText("No opportunities match this decision state"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("No ranked opportunities yet"),
    ).not.toBeInTheDocument();
  });

  it("does not report an empty queue when the server filter fails", async () => {
    const rows = [opportunity("1", "Promising idea", "promising")];
    vi.mocked(api.opportunities).mockImplementation(async (filters) => {
      if (filters?.reviewState) {
        throw new Error("Filtered queue unavailable");
      }
      return rows;
    });
    renderWithClient(<Dashboard />);

    expect(await screen.findByText("Promising idea")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Promising 1" }));

    expect(
      await screen.findByText("Could not load dashboard data"),
    ).toBeInTheDocument();
    expect(screen.getByText("Filtered queue unavailable")).toBeInTheDocument();
    expect(
      screen.queryByText("No opportunities match this decision state"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Current opportunity results unavailable"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "All 1" }));
    expect(await screen.findByText("Promising idea")).toBeInTheDocument();
    expect(
      screen.queryByText("Could not load dashboard data"),
    ).not.toBeInTheDocument();
  });

  it("does not present a failed base queue as an empty workspace", async () => {
    vi.mocked(api.opportunities).mockRejectedValue(
      new Error("Opportunity queue unavailable"),
    );
    renderWithClient(<Dashboard />);

    expect(
      await screen.findByText("Current opportunity results unavailable"),
    ).toBeInTheDocument();
    expect(screen.getByText("Opportunity queue unavailable")).toBeInTheDocument();
    expect(
      screen.queryByText("No ranked opportunities yet"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Review unavailable" }),
    ).toBeDisabled();
  });

  it("does not present a failed scope filter as an empty review queue", async () => {
    const rows = [opportunity("1", "New idea", "new")];
    vi.mocked(api.opportunities).mockImplementation(async (filters) => {
      if (filters?.evidenceSource) {
        throw new Error("Scoped queue unavailable");
      }
      return rows;
    });
    renderWithClient(<Dashboard />);

    expect(await screen.findByText("New idea")).toBeInTheDocument();
    fireEvent.change(
      screen.getByRole("combobox", { name: "Evidence source" }),
      { target: { value: "github" } },
    );

    expect(
      await screen.findByText("Current opportunity results unavailable"),
    ).toBeInTheDocument();
    expect(screen.getByText("Scoped queue unavailable")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Review unavailable" }),
    ).toBeDisabled();
    expect(
      screen.queryByText("Showing 0 of 0 current opportunities"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("No current opportunities match these filters"),
    ).not.toBeInTheDocument();
  });

  it("applies accessible queue filters and links to the next new item", async () => {
    const rows = [
      opportunity("1", "Highest-ranked new idea", "new"),
      opportunity("2", "Promising idea", "promising"),
    ];
    vi.mocked(api.opportunities).mockImplementation(async (filters) =>
      filters?.projectId ? [rows[0]] : rows,
    );
    renderWithClient(<Dashboard />);

    expect(
      await screen.findByRole("group", { name: "Queue filters" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("option", { name: "CI research" }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Project" }), {
      target: { value: "project-1" },
    });
    fireEvent.change(
      screen.getByRole("combobox", { name: "Evidence source" }),
      { target: { value: "github" } },
    );
    fireEvent.change(screen.getByRole("combobox", { name: "Readiness" }), {
      target: { value: "medium" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Snapshot age" }), {
      target: { value: "30" },
    });

    await waitFor(() =>
      expect(api.opportunities).toHaveBeenLastCalledWith({
        currentOnly: true,
        projectId: "project-1",
        evidenceSource: "github",
        readiness: "medium",
        maxAgeDays: 30,
      }),
    );
    expect(
      await screen.findByRole("link", { name: /Review next/ }),
    ).toHaveAttribute("href", "/opportunities/1");
    expect(
      await screen.findByText("Showing 1 of 1 current opportunities"),
    ).toHaveAttribute("aria-live", "polite");
    expect(screen.getByRole("button", { name: "All 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New 1" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByRole("combobox", { name: "Project" })).toHaveValue(
      "all",
    );
    expect(
      screen.getByRole("combobox", { name: "Evidence source" }),
    ).toHaveValue("all");
    expect(screen.getByRole("combobox", { name: "Readiness" })).toHaveValue(
      "all",
    );
    expect(screen.getByRole("combobox", { name: "Snapshot age" })).toHaveValue(
      "all",
    );
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeDisabled();
  });
});
