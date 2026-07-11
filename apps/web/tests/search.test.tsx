import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SemanticSearch } from "../src/features/search";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: {
    semanticSearch: vi.fn(),
  },
}));

function renderFeature() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SemanticSearch />
    </QueryClientProvider>,
  );
}

describe("SemanticSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.semanticSearch).mockResolvedValue({
      evidence_hits: [
        {
          id: "evidence-1",
          source: "github",
          title: "CI logs are hard to diagnose",
          excerpt: "Maintainers repeatedly lose time reading raw CI output.",
          source_url: "https://github.com/example/repo/issues/1",
          match_score: 0.91,
          signal_type: "pain_point",
          review_label: "true_signal",
          created_at: "2026-07-11T10:00:00Z",
          untrusted_evidence: true,
          provenance: {
            evidence_hash: "a".repeat(64),
            scan_ids: ["scan-1"],
            run_ids: ["run-1"],
            project_ids: ["project-1"],
            observations: [],
          },
        },
      ],
      opportunity_threads: [
        {
          id: "thread-1",
          project_id: "project-1",
          title: "CI diagnosis workbench",
          summary: "A focused workflow for recurring CI diagnosis pain.",
          match_score: 0.86,
          matched_evidence_ids: ["evidence-1"],
          matched_evidence_count: 1,
          review_state: "build_candidate",
          lineage_status: "complete",
          evidence_readiness: {
            level: "strong",
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
              "enough_evidence",
              "source_diversity",
              "source_url_coverage",
              "human_review_coverage",
            ],
            gaps: [],
          },
          provenance: {
            snapshot_id: "snapshot-1",
            run_id: "run-1",
            scan_id: "scan-1",
            evidence_hash: "a".repeat(64),
            content_hash: "b".repeat(64),
            match_method: "weighted_similarity",
            match_confidence: 0.86,
          },
        },
      ],
    });
  });

  it("renders typed evidence hits and related opportunity threads", async () => {
    renderFeature();

    fireEvent.click(screen.getByRole("button", { name: "Search evidence" }));

    await waitFor(() => expect(api.semanticSearch).toHaveBeenCalled());
    expect(vi.mocked(api.semanticSearch).mock.calls[0][0]).toBe(
      "weekly spreadsheet client report",
    );
    expect(
      await screen.findByText("CI logs are hard to diagnose"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Maintainers repeatedly lose time reading raw CI output.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("CI diagnosis workbench")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open opportunity thread" }),
    ).toHaveAttribute("href", "/threads/thread-1");
  });
});
