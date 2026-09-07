import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SemanticSearch } from "../src/features/search";
import { api } from "../src/lib/api";
import type { SemanticSearch as SemanticSearchResults } from "../src/lib/types";

vi.mock("../src/lib/api", () => ({ api: { semanticSearch: vi.fn() } }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

const populatedResults: SemanticSearchResults = {
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
};

const emptyResults: SemanticSearchResults = {
  evidence_hits: [],
  opportunity_threads: [],
};

function renderFeature() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree = () => (
    <QueryClientProvider client={client}>
      <SemanticSearch />
    </QueryClientProvider>
  );
  const view = render(tree());
  return { ...view, rerenderFeature: () => view.rerender(tree()) };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

describe("SemanticSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/search");
    vi.mocked(api.semanticSearch).mockResolvedValue(populatedResults);
  });

  it("renders typed evidence hits and grouped opportunity threads", async () => {
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
      screen.getByText("2 results for “weekly spreadsheet client report”"),
    ).toBeInTheDocument();
    expect(screen.getByText("1 matched evidence record")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open opportunity thread" }),
    ).toHaveAttribute("href", "/threads/thread-1");
    expect(window.location.search).toBe("?q=weekly+spreadsheet+client+report");
  });

  it("restores and runs a shareable query from the URL", async () => {
    window.history.replaceState({}, "", "/search?q=customer+onboarding");
    renderFeature();

    expect(
      screen.getByRole("textbox", { name: "Search the evidence library" }),
    ).toHaveValue("customer onboarding");
    await waitFor(() =>
      expect(api.semanticSearch).toHaveBeenCalledWith("customer onboarding"),
    );
    expect(
      await screen.findByText("CI logs are hard to diagnose"),
    ).toBeInTheDocument();
  });

  it("runs a new query delivered to an already-mounted search route", async () => {
    const view = renderFeature();
    expect(api.semanticSearch).not.toHaveBeenCalled();

    window.history.replaceState({}, "", "/search?q=reports+and+exports");
    view.rerenderFeature();

    await waitFor(() =>
      expect(api.semanticSearch).toHaveBeenCalledWith("reports and exports"),
    );
    expect(
      screen.getByRole("textbox", { name: "Search the evidence library" }),
    ).toHaveValue("reports and exports");
    expect(
      await screen.findByText("2 results for “reports and exports”"),
    ).toBeInTheDocument();
  });

  it("submits with Enter and shows an actionable empty state", async () => {
    vi.mocked(api.semanticSearch).mockResolvedValue(emptyResults);
    renderFeature();
    const input = screen.getByRole("textbox", {
      name: "Search the evidence library",
    });

    fireEvent.change(input, { target: { value: "  invoice follow-up  " } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() =>
      expect(api.semanticSearch).toHaveBeenCalledWith("invoice follow-up"),
    );
    expect(
      await screen.findByText("No results for “invoice follow-up”"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Try a broader example" }),
    ).toBeEnabled();
  });

  it("keeps prior results visible while a later search is pending", async () => {
    renderFeature();
    fireEvent.click(screen.getByRole("button", { name: "Search evidence" }));
    expect(
      await screen.findByText("CI logs are hard to diagnose"),
    ).toBeInTheDocument();

    const pending = deferred<SemanticSearchResults>();
    vi.mocked(api.semanticSearch).mockReturnValueOnce(pending.promise);
    fireEvent.change(
      screen.getByRole("textbox", { name: "Search the evidence library" }),
      {
        target: { value: "release notes" },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Search evidence" }));

    expect(
      await screen.findByText("Updating search results"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("CI logs are hard to diagnose"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("2 results for “weekly spreadsheet client report”"),
    ).toBeInTheDocument();
    pending.resolve(emptyResults);
    expect(
      await screen.findByText("No results for “release notes”"),
    ).toBeInTheDocument();
  });

  it("ignores a late response from an older request", async () => {
    const first = deferred<SemanticSearchResults>();
    const second = deferred<SemanticSearchResults>();
    vi.mocked(api.semanticSearch)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    renderFeature();
    const input = screen.getByRole("textbox", {
      name: "Search the evidence library",
    });

    fireEvent.change(input, { target: { value: "first query" } });
    fireEvent.submit(input.closest("form")!);
    fireEvent.change(input, { target: { value: "second query" } });
    fireEvent.submit(input.closest("form")!);

    second.resolve(populatedResults);
    expect(
      await screen.findByText("2 results for “second query”"),
    ).toBeInTheDocument();
    first.resolve(emptyResults);

    await waitFor(() =>
      expect(
        screen.queryByText("No results for “first query”"),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByText("2 results for “second query”"),
    ).toBeInTheDocument();
  });

  it("shows an error with a working retry action", async () => {
    vi.mocked(api.semanticSearch)
      .mockRejectedValueOnce(new Error("Embedding service unavailable"))
      .mockResolvedValueOnce(populatedResults);
    renderFeature();
    fireEvent.click(screen.getByRole("button", { name: "Search evidence" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Embedding service unavailable",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry search" }));

    expect(
      await screen.findByText("CI logs are hard to diagnose"),
    ).toBeInTheDocument();
    expect(api.semanticSearch).toHaveBeenCalledTimes(2);
  });
});
