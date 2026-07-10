import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Evaluation } from "../src/features/evaluation";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({ api: { evaluation: vi.fn() } }));

function renderEvaluation() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><Evaluation /></QueryClientProvider>);
}

const zeroCounts = {
  true_signal: 0,
  false_positive: 0,
  unclear: 0,
  duplicate: 0,
  not_actionable: 0,
  sensitive_risk: 0,
};

describe("Evaluation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders reviewed precision including a valid zero", async () => {
    vi.mocked(api.evaluation).mockResolvedValue({
      total_reviewable_items: 4,
      reviewed_items: 1,
      review_coverage: 0.25,
      label_counts: { ...zeroCounts, false_positive: 1 },
      unrecognized_latest_labels: 0,
      precision_on_reviewed_positives: 0,
      by_source: {
        github: {
          total_items: 4,
          reviewed_items: 1,
          review_coverage: 0.25,
          label_counts: { ...zeroCounts, false_positive: 1 },
          precision_on_reviewed_positives: 0,
        },
      },
      by_signal_type: {},
      selection_bias_warning: "Metrics describe only manually reviewed evidence and may not represent all detected items.",
    });
    renderEvaluation();

    expect(await screen.findByText("Evidence evaluation")).toBeInTheDocument();
    const precisionTile = screen.getByText("Reviewed precision").closest("section");
    expect(precisionTile).not.toBeNull();
    expect(within(precisionTile!).getByText("0%")).toBeInTheDocument();
    expect(screen.getByText(/may not represent all detected items/)).toBeInTheDocument();
    expect(screen.getByText(/Recall and F1 are not reported/)).toBeInTheDocument();
    expect(screen.queryByText("Not defined")).not.toBeInTheDocument();
  });

  it("separates no evidence from evidence with no reviews", async () => {
    vi.mocked(api.evaluation).mockResolvedValue({
      total_reviewable_items: 0,
      reviewed_items: 0,
      review_coverage: 0,
      label_counts: zeroCounts,
      unrecognized_latest_labels: 0,
      precision_on_reviewed_positives: null,
      by_source: {},
      by_signal_type: {},
      selection_bias_warning: "Metrics describe only manually reviewed evidence and may not represent all detected items.",
    });
    const view = renderEvaluation();
    expect(await screen.findByText("No reviewable evidence yet")).toBeInTheDocument();
    expect(screen.getByText(/Recall and F1 are not reported/)).toBeInTheDocument();
    view.unmount();

    vi.mocked(api.evaluation).mockResolvedValue({
      total_reviewable_items: 4,
      reviewed_items: 0,
      review_coverage: 0,
      label_counts: zeroCounts,
      unrecognized_latest_labels: 0,
      precision_on_reviewed_positives: null,
      by_source: {},
      by_signal_type: {},
      selection_bias_warning: "Metrics describe only manually reviewed evidence and may not represent all detected items.",
    });
    renderEvaluation();
    expect(await screen.findByText("Evidence is ready for review")).toBeInTheDocument();
    expect(screen.getByText("Not defined")).toBeInTheDocument();
  });

  it("renders backend error details", async () => {
    vi.mocked(api.evaluation).mockRejectedValue(
      new Error(JSON.stringify({ detail: "Evaluation is unavailable." })),
    );
    renderEvaluation();

    expect(
      await screen.findByText("Could not load evidence evaluation"),
    ).toBeInTheDocument();
    expect(screen.getByText("Evaluation is unavailable.")).toBeInTheDocument();
  });
});
