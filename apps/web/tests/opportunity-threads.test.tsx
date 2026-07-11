import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OpportunityThreadDetail } from "../src/features/opportunity-thread-detail";
import { OpportunityThreads } from "../src/features/opportunity-threads";
import { api } from "../src/lib/api";
import type { Opportunity, OpportunityThread } from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  api: {
    opportunityThreads: vi.fn(),
    opportunityThread: vi.fn(),
    updateOpportunityThreadDecision: vi.fn(),
    detachOpportunitySnapshot: vi.fn(),
    buildPackets: vi.fn(),
    createBuildPacket: vi.fn(),
    buildPacket: vi.fn(),
    verifyBuildPacket: vi.fn(),
    downloadBuildPacket: vi.fn(),
  },
}));

const readiness = {
  level: "strong" as const,
  evidence_count: 6,
  source_count: 2,
  safe_url_count: 6,
  reviewed_count: 4,
  source_url_coverage: 1,
  human_review_coverage: 0.67,
  checks: {
    enough_evidence: true,
    source_diversity: true,
    source_url_coverage: true,
    human_review_coverage: true,
  },
  passed_checks: [
    "enough_evidence" as const,
    "source_diversity" as const,
    "source_url_coverage" as const,
    "human_review_coverage" as const,
  ],
  gaps: [],
};

function snapshot(id: string, current = false): Opportunity {
  return {
    id,
    thread_id: "thread-1",
    run_id: current ? "run-2" : "run-1",
    scan_id: current ? "scan-2" : "scan-1",
    cluster_id: `cluster-${id}`,
    evidence_hash: "a".repeat(64),
    content_hash: "b".repeat(64),
    match_method: current ? "centroid_composite" : "new_thread",
    match_confidence: current ? 0.86 : null,
    match_margin: current ? 0.12 : null,
    centroid_similarity: current ? 0.9 : null,
    evidence_jaccard: current ? 0.7 : null,
    title_jaccard: current ? 0.8 : null,
    embedding_model: "fixture-embed-v1",
    embedding_backend: "fixture",
    title: current ? "Recurring CI diagnosis pain" : "CI diagnosis pain",
    problem_statement: "Maintainers cannot understand failures quickly.",
    target_user: "Indie maintainers",
    current_workaround: "Read raw logs",
    suggested_mvp: "Local evidence-aware diagnosis tool",
    why_now: "Repeated public evidence",
    feasibility_score: 0.82,
    opportunity_score: 0.78,
    competition_notes: "Narrow wedge",
    scoring_breakdown_json: {},
    generated_prompt: "# Build",
    review_state: "build_candidate",
    review_note: null,
    decision_updated_at: "2026-07-11T11:00:00Z",
    created_at: current ? "2026-07-11T10:00:00Z" : "2026-07-10T10:00:00Z",
    updated_at: "2026-07-11T10:00:00Z",
    evidence_items: [],
    signal_count: 6,
    top_source: "github",
    evidence_readiness: readiness,
  };
}

const thread: OpportunityThread = {
  id: "thread-1",
  project_id: "project-1",
  lineage_status: "complete",
  review_state: "build_candidate",
  review_note: null,
  decision_updated_at: "2026-07-11T11:00:00Z",
  version: 3,
  snapshot_count: 2,
  current_snapshot: snapshot("snapshot-2", true),
  snapshots: [snapshot("snapshot-2", true), snapshot("snapshot-1")],
  decision_history: [],
  created_at: "2026-07-10T10:00:00Z",
  updated_at: "2026-07-11T10:00:00Z",
};

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("Opportunity threads", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.opportunityThreads).mockResolvedValue([thread]);
    vi.mocked(api.opportunityThread).mockResolvedValue(thread);
    vi.mocked(api.buildPackets).mockResolvedValue([]);
    vi.mocked(api.createBuildPacket).mockResolvedValue({
      id: "packet-1",
      project_id: "project-1",
      run_id: "run-2",
      thread_id: "thread-1",
      snapshot_id: "snapshot-2",
      lineage_status: "complete",
      generation_mode: "deterministic",
      schema_version: "1",
      tasksignal_version: "1.0.0",
      template_version: "1",
      generated_at: "2026-07-11T12:00:00Z",
      enhancement_status: "not_requested",
      enhancement_provider: null,
      enhancement_model: null,
      enhancement_template_version: null,
      artifacts: [
        {
          path: "README.md",
          content: "# Packet",
          byte_count: 8,
          sha256: "c".repeat(64),
        },
      ],
      manifest: {},
      manifest_sha256: "d".repeat(64),
      created_at: "2026-07-11T12:00:00Z",
    });
    vi.mocked(api.verifyBuildPacket).mockResolvedValue({
      packet_id: "packet-1",
      valid: true,
      errors: [],
      missing_files: [],
      unexpected_files: [],
      mismatched_files: [],
    });
  });

  it("filters threads on the server and exposes match confidence", async () => {
    renderWithClient(<OpportunityThreads />);

    expect(
      await screen.findByText("Recurring CI diagnosis pain"),
    ).toBeInTheDocument();
    expect(screen.getByText("86% confidence")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Review state" }), {
      target: { value: "build_candidate" },
    });
    await waitFor(() =>
      expect(api.opportunityThreads).toHaveBeenLastCalledWith({
        reviewState: "build_candidate",
      }),
    );
  });

  it("creates, verifies, and downloads a deterministic build packet", async () => {
    renderWithClient(<OpportunityThreadDetail id="thread-1" />);

    expect(await screen.findByText("Build Studio")).toBeInTheDocument();
    expect(screen.getAllByText("centroid composite").length).toBeGreaterThan(0);
    fireEvent.click(
      screen.getByRole("button", { name: "Generate deterministic packet" }),
    );
    await waitFor(() =>
      expect(api.createBuildPacket).toHaveBeenCalledWith("thread-1", {
        expected_version: 3,
        use_configured_ai: false,
      }),
    );
    expect((await screen.findAllByText("README.md")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Verify packet" }));
    expect(await screen.findByText("Integrity verified")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Download ZIP" }));
    await waitFor(() => expect(api.downloadBuildPacket).toHaveBeenCalled());
    expect(vi.mocked(api.downloadBuildPacket).mock.calls[0][0]).toBe("packet-1");
  });

  it("offers a human correction for a historical snapshot", async () => {
    vi.mocked(api.detachOpportunitySnapshot).mockResolvedValue({
      source_thread: {
        ...thread,
        snapshots: [thread.snapshots[0]],
        snapshot_count: 1,
        version: 4,
      },
      new_thread: {
        ...thread,
        id: "thread-2",
        snapshots: [thread.snapshots[1]],
        current_snapshot: thread.snapshots[1],
        snapshot_count: 1,
        version: 1,
      },
    });
    renderWithClient(<OpportunityThreadDetail id="thread-1" />);

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Detach snapshot into a new thread",
      }),
    );
    await waitFor(() =>
      expect(api.detachOpportunitySnapshot).toHaveBeenCalledWith(
        "thread-1",
        "snapshot-1",
        3,
      ),
    );
  });
});
