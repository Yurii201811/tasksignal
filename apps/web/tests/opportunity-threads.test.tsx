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
import { OpportunityThreadDetail } from "../src/features/opportunity-thread-detail";
import { OpportunityThreads } from "../src/features/opportunity-threads";
import { api } from "../src/lib/api";
import type {
  BuildPacket,
  BuildPacketSummary,
  EvidenceItem,
  Opportunity,
  OpportunityThread,
} from "../src/lib/types";

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
    match_method: current ? "weighted_similarity" : "new_thread",
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

function packet(id: string): BuildPacket {
  return {
    id,
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
        content: `# ${id}`,
        byte_count: id.length + 2,
        sha256: "c".repeat(64),
      },
    ],
    manifest: {},
    manifest_sha256: "d".repeat(64),
    created_at: "2026-07-11T12:00:00Z",
  };
}

function packetSummary(id: string): BuildPacketSummary {
  const value = packet(id);
  return {
    ...value,
    artifact_count: value.artifacts.length,
    total_bytes: value.artifacts[0].byte_count,
  };
}

function evidenceItem(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: "evidence-1",
    source: "github",
    external_id: "issue-1",
    url: "https://github.com/example/repo/issues/1",
    title: "Sensitive workflow",
    body: "Public evidence",
    score: 10,
    comments_count: 2,
    created_at: "2026-07-11T09:00:00Z",
    tags: [],
    signal_type: "pain_point",
    pain_score: 0.8,
    task_concreteness_score: 0.7,
    buying_intent_score: 0.2,
    evidence_spans: [],
    review_label: "true_signal",
    review_note: null,
    reviewed_at: "2026-07-11T10:00:00Z",
    review_version: 1,
    review_history_count: 1,
    agent_review_label: "sensitive_risk",
    agent_reviewed_at: "2026-07-11T10:01:00Z",
    agent_review_history_count: 1,
    agent_review_version: 2,
    agent_session_id: "session-1",
    ...overrides,
  };
}

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
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(api.opportunityThreads).mockResolvedValue([thread]);
    vi.mocked(api.opportunityThread).mockResolvedValue(thread);
    vi.mocked(api.buildPackets).mockResolvedValue([]);
    vi.mocked(api.createBuildPacket).mockResolvedValue(packet("packet-1"));
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
    expect(screen.getAllByText("weighted similarity").length).toBeGreaterThan(
      0,
    );
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
    expect(vi.mocked(api.downloadBuildPacket).mock.calls[0][0]).toBe(
      "packet-1",
    );
  });

  it("offers a confirmed human correction only for automatically matched snapshots", async () => {
    vi.mocked(api.detachOpportunitySnapshot).mockResolvedValue({
      source_thread: {
        ...thread,
        current_snapshot: thread.snapshots[1],
        snapshots: [thread.snapshots[1]],
        snapshot_count: 1,
        version: 4,
      },
      new_thread: {
        ...thread,
        id: "thread-2",
        snapshots: [thread.snapshots[0]],
        current_snapshot: thread.snapshots[0],
        snapshot_count: 1,
        version: 1,
      },
    });
    renderWithClient(<OpportunityThreadDetail id="thread-1" />);

    const initialSnapshot = (
      await screen.findByText("CI diagnosis pain")
    ).closest("article");
    expect(initialSnapshot).not.toBeNull();
    expect(
      within(initialSnapshot as HTMLElement).queryByRole("button", {
        name: "Detach snapshot into a new thread",
      }),
    ).not.toBeInTheDocument();
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Detach snapshot into a new thread",
      }),
    );
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() =>
      expect(api.detachOpportunitySnapshot).toHaveBeenCalledWith(
        "thread-1",
        "snapshot-2",
        3,
      ),
    );
    expect(
      await screen.findByRole("link", { name: "Open detached thread" }),
    ).toHaveFocus();
  });

  it("refreshes a stale decision version while preserving unsaved human input", async () => {
    const refreshed = { ...thread, version: 4 };
    vi.mocked(api.opportunityThread)
      .mockResolvedValueOnce(thread)
      .mockResolvedValue(refreshed);
    vi.mocked(api.updateOpportunityThreadDecision)
      .mockRejectedValueOnce(new Error('{"detail":"version conflict"}'))
      .mockResolvedValue({
        ...refreshed,
        version: 5,
        review_state: "promising",
        review_note: "Keep this operator note",
      });
    renderWithClient(<OpportunityThreadDetail id="thread-1" />);

    fireEvent.change(await screen.findByLabelText("Review state"), {
      target: { value: "promising" },
    });
    fireEvent.change(screen.getByLabelText("Local review note"), {
      target: { value: "Keep this operator note" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save thread decision" }),
    );

    await waitFor(() => expect(api.opportunityThread).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("Local review note")).toHaveValue(
      "Keep this operator note",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Save thread decision" }),
    );
    await waitFor(() =>
      expect(api.updateOpportunityThreadDecision).toHaveBeenLastCalledWith(
        "thread-1",
        {
          review_state: "promising",
          review_note: "Keep this operator note",
          expected_version: 4,
        },
      ),
    );
  });

  it("refreshes a stale detach version before retrying", async () => {
    const refreshed = { ...thread, version: 4 };
    const result = {
      source_thread: {
        ...refreshed,
        current_snapshot: refreshed.snapshots[1],
        snapshots: [refreshed.snapshots[1]],
        snapshot_count: 1,
        version: 5,
      },
      new_thread: {
        ...thread,
        id: "thread-2",
        current_snapshot: refreshed.snapshots[0],
        snapshots: [refreshed.snapshots[0]],
        snapshot_count: 1,
        version: 1,
      },
    };
    vi.mocked(api.opportunityThread)
      .mockResolvedValueOnce(thread)
      .mockResolvedValue(refreshed);
    vi.mocked(api.detachOpportunitySnapshot)
      .mockRejectedValueOnce(new Error('{"detail":"version conflict"}'))
      .mockResolvedValue(result);
    renderWithClient(<OpportunityThreadDetail id="thread-1" />);

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Detach snapshot into a new thread",
      }),
    );
    await waitFor(() => expect(api.opportunityThread).toHaveBeenCalledTimes(2));
    fireEvent.click(
      screen.getByRole("button", { name: "Detach snapshot into a new thread" }),
    );
    await waitFor(() =>
      expect(api.detachOpportunitySnapshot).toHaveBeenLastCalledWith(
        "thread-1",
        "snapshot-2",
        4,
      ),
    );
  });

  it("blocks packet creation for an unresolved newer agent sensitive risk", async () => {
    const riskySnapshot = {
      ...thread.current_snapshot!,
      evidence_items: [evidenceItem()],
    };
    vi.mocked(api.opportunityThread).mockResolvedValue({
      ...thread,
      current_snapshot: riskySnapshot,
      snapshots: [riskySnapshot, thread.snapshots[1]],
    });
    renderWithClient(<OpportunityThreadDetail id="thread-1" />);

    expect(await screen.findByText("Eligibility blocked")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Generate deterministic packet" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Generate with configured AI" }),
    ).toBeDisabled();
    expect(screen.getByText(/newer agent-sensitive risk/i)).toBeInTheDocument();
  });

  it("does not carry a verification result to another packet", async () => {
    vi.mocked(api.buildPackets).mockResolvedValue([
      packetSummary("packet-1"),
      packetSummary("packet-2"),
    ]);
    vi.mocked(api.buildPacket).mockImplementation(async (id) => packet(id));
    renderWithClient(<OpportunityThreadDetail id="thread-1" />);

    const viewButtons = await screen.findAllByRole("button", {
      name: "View packet",
    });
    fireEvent.click(viewButtons[0]);
    expect(await screen.findByText("Packet packet-1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Verify packet" }));
    expect(await screen.findByText("Integrity verified")).toBeInTheDocument();

    fireEvent.click(viewButtons[1]);
    expect(await screen.findByText("Packet packet-2")).toBeInTheDocument();
    expect(screen.queryByText("Integrity verified")).not.toBeInTheDocument();
  });

  it("refreshes a stale packet version before retrying", async () => {
    const refreshed = { ...thread, version: 4 };
    vi.mocked(api.opportunityThread)
      .mockResolvedValueOnce(thread)
      .mockResolvedValue(refreshed);
    vi.mocked(api.createBuildPacket)
      .mockRejectedValueOnce(new Error('{"detail":"version conflict"}'))
      .mockResolvedValue(packet("packet-2"));
    renderWithClient(<OpportunityThreadDetail id="thread-1" />);

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Generate deterministic packet",
      }),
    );
    await waitFor(() => expect(api.opportunityThread).toHaveBeenCalledTimes(2));
    fireEvent.click(
      screen.getByRole("button", { name: "Generate deterministic packet" }),
    );
    await waitFor(() =>
      expect(api.createBuildPacket).toHaveBeenLastCalledWith("thread-1", {
        expected_version: 4,
        use_configured_ai: false,
      }),
    );
  });
});
