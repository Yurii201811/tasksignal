import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EvidenceReviewControl } from "../src/features/evidence-review-control";
import { api } from "../src/lib/api";
import type { EvidenceItem } from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  api: { createEvidenceReview: vi.fn() },
}));

const item: EvidenceItem = {
  id: "item-1",
  source: "hackernews",
  external_id: "1",
  url: "https://news.ycombinator.com/item?id=1",
  title: "AI code review",
  body: "We need production-readiness checks for AI-generated code.",
  score: 42,
  comments_count: 7,
  created_at: "2026-06-03T09:30:00.000Z",
  tags: ["ai", "code-review"],
  signal_type: "pain",
  pain_score: 0.9,
  task_concreteness_score: 0.8,
  buying_intent_score: 0.4,
  evidence_spans: ["need production-readiness checks"],
  review_label: null,
  review_note: null,
  reviewed_at: null,
  review_history_count: 0,
};

describe("EvidenceReviewControl", () => {
  beforeEach(() => vi.clearAllMocks());

  it("appends a review and invalidates every dependent query", async () => {
    vi.mocked(api.createEvidenceReview).mockResolvedValue({} as never);
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        <EvidenceReviewControl opportunityId="opportunity-1" item={item} />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText("Evidence label"), {
      target: { value: "true_signal" },
    });
    fireEvent.change(screen.getByLabelText("New evidence review note"), {
      target: { value: "Useful signal." },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Add evidence review" }),
    );

    await waitFor(() => {
      expect(api.createEvidenceReview).toHaveBeenCalledWith({
        item_id: "item-1",
        label: "true_signal",
        user_note: "Useful signal.",
      });
      for (const queryKey of [
        ["opportunity", "opportunity-1"],
        ["opportunities"],
        ["evaluation"],
        ["item-labels", "item-1"],
      ]) {
        expect(invalidate).toHaveBeenCalledWith({ queryKey });
      }
    });
    expect(screen.getByLabelText("New evidence review note")).toHaveAttribute(
      "maxlength",
      "500",
    );
    expect(screen.getByLabelText("New evidence review note")).toHaveValue("");
  });
});
