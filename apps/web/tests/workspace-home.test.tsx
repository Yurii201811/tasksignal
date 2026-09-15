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
import { WorkspaceHome } from "../src/features/workspace-home";
import { api } from "../src/lib/api";
import type {
  Opportunity,
  ProcessSummary,
  ResearchProject,
  Stats,
} from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  api: {
    stats: vi.fn(),
    opportunities: vi.fn(),
    researchProjects: vi.fn(),
    processDemo: vi.fn(),
  },
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function renderWithClient() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <WorkspaceHome />
      </QueryClientProvider>,
    ),
  };
}

const emptyStats: Stats = {
  total_items: 0,
  problem_signals: 0,
  clusters: 0,
  opportunities: 0,
  source_breakdown: [],
  pain_distribution: [],
};

const evidenceReadiness = {
  level: "medium" as const,
  evidence_count: 4,
  source_count: 2,
  safe_url_count: 4,
  reviewed_count: 1,
  source_url_coverage: 1,
  human_review_coverage: 0.25,
  checks: {
    enough_evidence: false,
    source_diversity: true,
    source_url_coverage: true,
    human_review_coverage: false,
  },
  passed_checks: ["source_diversity" as const, "source_url_coverage" as const],
  gaps: ["Collect 1 more evidence item."],
};

function opportunity(
  id: string,
  title: string,
  reviewState: Opportunity["review_state"],
  threadId: string | null = null,
): Opportunity {
  return {
    id,
    thread_id: threadId,
    cluster_id: `cluster-${id}`,
    title,
    problem_statement: `Evidence-backed problem for ${title}.`,
    target_user: "Maintainers",
    current_workaround: "Manual review",
    suggested_mvp: "Focused local tool",
    why_now: "Repeated recent evidence",
    feasibility_score: 0.8,
    opportunity_score: 0.75,
    competition_notes: "Narrow scope",
    scoring_breakdown_json: {},
    generated_prompt: "# Build",
    review_state: reviewState,
    review_note: null,
    decision_updated_at: null,
    created_at: "2026-09-08T09:00:00Z",
    updated_at: "2026-09-08T09:00:00Z",
    evidence_items: [],
    signal_count: 4,
    top_source: "github",
    evidence_readiness: evidenceReadiness,
  };
}

function project(id: string, name: string, updatedAt: string): ResearchProject {
  return {
    id,
    name,
    description: null,
    source_type: "github",
    query: `${name} pain`,
    limit: 30,
    cadence: "manual",
    schedule_interval_hours: null,
    labels: [],
    enabled: true,
    last_scan_id: null,
    last_scan_status: null,
    last_run_at: null,
    next_run_at: null,
    run_count: 2,
    created_at: "2026-09-01T09:00:00Z",
    updated_at: updatedAt,
  };
}

describe("WorkspaceHome", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.stats).mockResolvedValue(emptyStats);
    vi.mocked(api.opportunities).mockResolvedValue([]);
    vi.mocked(api.researchProjects).mockResolvedValue([]);
  });

  it("shows a loading overview before resolving to useful empty-state actions", async () => {
    const statsRequest = deferred<Stats>();
    const opportunitiesRequest = deferred<Opportunity[]>();
    const projectsRequest = deferred<ResearchProject[]>();
    vi.mocked(api.stats).mockReturnValue(statsRequest.promise);
    vi.mocked(api.opportunities).mockReturnValue(opportunitiesRequest.promise);
    vi.mocked(api.researchProjects).mockReturnValue(projectsRequest.promise);

    renderWithClient();

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading research overview",
    );
    expect(screen.getAllByText("—")).toHaveLength(7);
    expect(
      screen.queryByRole("link", { name: /New research project/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Create your first project/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Start with a question worth answering."),
    ).not.toBeInTheDocument();

    statsRequest.resolve(emptyStats);
    opportunitiesRequest.resolve([]);
    projectsRequest.resolve([]);

    expect(
      await screen.findByText("Start with a question worth answering."),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Try demo data" }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: /Create your first project/ }),
    ).toHaveAttribute("href", "/projects");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("reports live counts, requests current snapshots, and routes review work", async () => {
    vi.mocked(api.stats).mockResolvedValue({
      ...emptyStats,
      total_items: 24,
      problem_signals: 9,
      clusters: 5,
      opportunities: 7,
    });
    vi.mocked(api.opportunities).mockResolvedValue([
      opportunity("old", "Promising backlog item", "promising"),
      opportunity("new", "Unreviewed priority", "new", "thread-new"),
      opportunity("build", "Build-ready item", "build_candidate"),
      opportunity("extra", "Fourth item", "rejected"),
    ]);
    vi.mocked(api.researchProjects).mockResolvedValue([
      project("old", "Old project", "2026-09-01T10:00:00Z"),
      project("middle", "Middle project", "2026-09-04T10:00:00Z"),
      project("newest", "Newest project", "2026-09-08T10:00:00Z"),
      project("recent", "Recent project", "2026-09-06T10:00:00Z"),
    ]);

    renderWithClient();

    expect(await screen.findByText("Unreviewed priority")).toBeInTheDocument();
    expect(api.opportunities).toHaveBeenCalledWith({ currentOnly: true });

    const overview = screen.getByRole("region", { name: "Workspace overview" });
    expect(
      within(screen.getByText("Evidence collected").closest("div")!).getByText(
        "24",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByText("Problem signals").closest("div")!).getByText(
        "9",
      ),
    ).toBeInTheDocument();
    expect(
      within(
        within(overview).getByText("Current opportunities").closest("div")!,
      ).getByText("4"),
    ).toBeInTheDocument();

    const reviewSection = screen
      .getByRole("heading", {
        name: "Ready for your attention",
      })
      .closest("section")!;
    expect(
      within(reviewSection)
        .getAllByRole("heading", { level: 3 })
        .map((node) => node.textContent),
    ).toEqual([
      "Unreviewed priority",
      "Build-ready item",
      "Promising backlog item",
    ]);
    expect(
      within(reviewSection).getByRole("link", { name: /Unreviewed priority/ }),
    ).toHaveAttribute("href", "/opportunities/new?queue=");
    expect(
      within(reviewSection).getByRole("link", {
        name: /Promising backlog item/,
      }),
    ).toHaveAttribute("href", "/opportunities/old?queue=");

    expect(
      screen.getByRole("link", { name: /Open decision queue/ }),
    ).toHaveAttribute("href", "/dashboard");
    expect(
      screen.getByRole("link", { name: /Newest project/ }),
    ).toHaveAttribute("href", "/projects/newest");
    expect(screen.queryByText("Old project")).not.toBeInTheDocument();
  });

  it("surfaces API errors and retries every workspace query", async () => {
    vi.mocked(api.stats)
      .mockRejectedValueOnce(new Error('{"detail":"Statistics unavailable"}'))
      .mockResolvedValue(emptyStats);

    renderWithClient();

    expect(
      await screen.findByText("Could not load your workspace"),
    ).toBeInTheDocument();
    expect(screen.getByText("Statistics unavailable")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => {
      expect(api.stats).toHaveBeenCalledTimes(2);
      expect(api.opportunities).toHaveBeenCalledTimes(2);
      expect(api.researchProjects).toHaveBeenCalledTimes(2);
    });
    await waitFor(() =>
      expect(
        screen.queryByText("Could not load your workspace"),
      ).not.toBeInTheDocument(),
    );
  });

  it("locks demo actions, confirms completion, and refreshes dependent data", async () => {
    const demoRequest = deferred<ProcessSummary>();
    vi.mocked(api.processDemo).mockReturnValue(demoRequest.promise);
    const { client } = renderWithClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");

    const demoButtons = await screen.findAllByRole("button", {
      name: "Try demo data",
    });
    fireEvent.click(demoButtons[0]);
    expect(
      await screen.findByRole("button", { name: "Preparing demo…" }),
    ).toBeDisabled();

    demoRequest.resolve({
      raw_items_loaded: 12,
      normalized_items_created: 12,
      signals_detected: 6,
      clusters_created: 3,
      opportunities_created: 2,
    });

    expect(
      await screen.findByText("Demo evidence is ready"),
    ).toBeInTheDocument();
    await waitFor(() => {
      for (const queryKey of [
        ["stats"],
        ["opportunities"],
        ["scans"],
        ["readiness"],
        ["opportunity-threads"],
        ["sources"],
      ]) {
        expect(invalidate).toHaveBeenCalledWith({ queryKey });
      }
    });
  });
});
