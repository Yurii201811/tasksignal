import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectRunHistory } from "../src/features/project-run-history";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: {
    researchProject: vi.fn(),
    researchProjectRuns: vi.fn(),
    researchProjectRunDelta: vi.fn(),
  },
}));

function renderFeature() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ProjectRunHistory id="project-1" />
    </QueryClientProvider>,
  );
}

describe("ProjectRunHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.researchProject).mockResolvedValue({
      id: "project-1",
      name: "Track workflow pain",
      description: null,
      source_type: "hackernews",
      query: "ask",
      limit: 30,
      cadence: "manual",
      schedule_interval_hours: null,
      labels: [],
      enabled: true,
      last_scan_id: "scan-2",
      last_scan_status: "completed",
      last_run_at: "2026-07-11T10:00:00Z",
      next_run_at: null,
      run_count: 2,
      created_at: "2026-07-10T10:00:00Z",
      updated_at: "2026-07-11T10:00:00Z",
    });
    vi.mocked(api.researchProjectRuns).mockResolvedValue([
      {
        id: "run-2",
        project_id: "project-1",
        scan_id: "scan-2",
        sequence: 2,
        source_type: "hackernews",
        source_origin: "https://news.ycombinator.com",
        query: "ask",
        requested_limit: 30,
        lineage_status: "complete",
        scan_status: "completed",
        started_at: "2026-07-11T10:00:00Z",
        finished_at: "2026-07-11T10:01:00Z",
        items_found: 8,
        items_saved: 2,
        signals_detected: 3,
        clusters_created: 1,
        opportunities_created: 1,
        created_at: "2026-07-11T10:00:00Z",
      },
      {
        id: "legacy-scan",
        project_id: "project-1",
        scan_id: "legacy-scan",
        sequence: null,
        source_type: "hackernews",
        source_origin: null,
        query: "ask",
        requested_limit: null,
        lineage_status: "untracked",
        scan_status: "completed",
        started_at: "2026-07-10T10:00:00Z",
        finished_at: "2026-07-10T10:01:00Z",
        items_found: 4,
        items_saved: 4,
        signals_detected: 1,
        clusters_created: 1,
        opportunities_created: 1,
        created_at: "2026-07-10T10:00:00Z",
      },
    ]);
    vi.mocked(api.researchProjectRunDelta).mockResolvedValue({
      project_id: "project-1",
      run_id: "run-2",
      scan_id: "scan-2",
      sequence: 2,
      previous_run_id: "run-1",
      evidence_changes: {
        new: 2,
        seen_before: 6,
        updated: 1,
        unchanged: 5,
        not_observed_this_run: 3,
      },
      signal_changes: {
        new: 1,
        seen_before: 2,
        updated: 0,
        unchanged: 2,
        not_observed_this_run: 1,
      },
      generated_snapshots: { clusters: 1, opportunities: 1 },
      opportunity_changes: {
        new: 0,
        updated: 1,
        unchanged: 0,
        not_observed_this_run: 0,
      },
      warnings: [],
    });
  });

  it("shows immutable runs and a precisely worded delta", async () => {
    renderFeature();

    expect(await screen.findByText("Track workflow pain")).toBeInTheDocument();
    expect(screen.getByText("Lineage untracked")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Compare run 2" }));

    expect(await screen.findByText("Evidence changes")).toBeInTheDocument();
    for (const label of [
      "New",
      "Seen before",
      "Updated",
      "Unchanged",
      "Not observed this run",
    ]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(
      screen.getByText(/absence never means deletion or resolution/i),
    ).toBeInTheDocument();
    expect(api.researchProjectRunDelta).toHaveBeenCalledWith(
      "project-1",
      "run-2",
    );
  });
});
