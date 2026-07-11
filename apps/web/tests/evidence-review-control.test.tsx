import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EvidenceReviewControl } from "../src/features/evidence-review-control";
import { api } from "../src/lib/api";
import type { EvidenceItem } from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  api: { createEvidenceReview: vi.fn() },
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

  it("renders the exact evidence-review value and label options", () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <EvidenceReviewControl opportunityId="opportunity-1" item={item} />
      </QueryClientProvider>,
    );

    const select = screen.getByLabelText("Evidence label") as HTMLSelectElement;
    expect(
      Array.from(select.options, (option) => [option.value, option.label]),
    ).toEqual([
      ["", "Select a label"],
      ["true_signal", "True signal"],
      ["false_positive", "False positive"],
      ["unclear", "Unclear"],
      ["duplicate", "Duplicate"],
      ["not_actionable", "Not actionable"],
      ["sensitive_risk", "Sensitive risk"],
    ]);
    expect(select).toHaveValue("");
    expect(
      screen.getByRole("button", { name: "Add evidence review" }),
    ).toBeDisabled();
  });

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
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Evidence review added",
    );

    fireEvent.change(screen.getByLabelText("Evidence label"), {
      target: { value: "false_positive" },
    });
    expect(screen.getByLabelText("Evidence label")).toHaveValue(
      "false_positive",
    );
    expect(screen.queryByText("Evidence review added")).not.toBeInTheDocument();
  });

  it("locks the submitted evidence draft until the request settles", async () => {
    const request = deferred<never>();
    vi.mocked(api.createEvidenceReview).mockReturnValue(request.promise);
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <EvidenceReviewControl opportunityId="opportunity-1" item={item} />
      </QueryClientProvider>,
    );
    const label = screen.getByLabelText("Evidence label");
    const note = screen.getByLabelText("New evidence review note");
    fireEvent.change(label, { target: { value: "unclear" } });
    fireEvent.change(note, { target: { value: "Submitted evidence draft" } });
    fireEvent.click(
      screen.getByRole("button", { name: "Add evidence review" }),
    );

    await waitFor(() => expect(api.createEvidenceReview).toHaveBeenCalled());
    expect(label).toBeDisabled();
    expect(note).toBeDisabled();
    label.focus();
    expect(label).not.toHaveFocus();
    note.focus();
    expect(note).not.toHaveFocus();
    expect(label).toHaveValue("unclear");
    expect(note).toHaveValue("Submitted evidence draft");

    request.reject(new Error("Request failed"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Evidence review was not saved",
    );
    expect(label).toBeEnabled();
    expect(note).toBeEnabled();
    expect(label).toHaveValue("unclear");
    expect(note).toHaveValue("Submitted evidence draft");
  });

  it("retains current evidence and the rejected draft without invalidating", async () => {
    const request = deferred<never>();
    vi.mocked(api.createEvidenceReview).mockReturnValue(request.promise);
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const reviewedItem: EvidenceItem = {
      ...item,
      review_label: "unclear",
      review_note: "Existing operator note.",
      reviewed_at: "2026-06-03T10:15:00.000Z",
      review_history_count: 2,
    };
    render(
      <QueryClientProvider client={client}>
        <EvidenceReviewControl
          opportunityId="opportunity-1"
          item={reviewedItem}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByLabelText("Evidence label")).toHaveValue("unclear");

    fireEvent.change(screen.getByLabelText("Evidence label"), {
      target: { value: "sensitive_risk" },
    });
    fireEvent.change(screen.getByLabelText("New evidence review note"), {
      target: { value: "Needs privacy review." },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Add evidence review" }),
    );

    await waitFor(() => {
      expect(api.createEvidenceReview).toHaveBeenCalledWith({
        item_id: "item-1",
        label: "sensitive_risk",
        user_note: "Needs privacy review.",
      });
    });
    expect(
      screen.getByText("Unclear", { selector: "span" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Current note: Existing operator note."),
    ).toBeInTheDocument();
    expect(screen.getByText("2 stored review(s)")).toBeInTheDocument();
    expect(screen.queryByText("Evidence review added")).not.toBeInTheDocument();
    expect(invalidate).not.toHaveBeenCalled();

    request.reject(
      new Error(JSON.stringify({ detail: "Could not add evidence review." })),
    );

    expect(
      await screen.findByText("Could not add evidence review."),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Evidence review was not saved",
    );
    expect(screen.getByLabelText("Evidence label")).toHaveValue(
      "sensitive_risk",
    );
    expect(screen.getByLabelText("New evidence review note")).toHaveValue(
      "Needs privacy review.",
    );
    expect(
      screen.getByText("Unclear", { selector: "span" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Current note: Existing operator note."),
    ).toBeInTheDocument();
    expect(screen.getByText("2 stored review(s)")).toBeInTheDocument();
    expect(screen.queryByText("Evidence review added")).not.toBeInTheDocument();
    expect(invalidate).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("New evidence review note"), {
      target: { value: "Revised privacy note." },
    });
    expect(screen.getByLabelText("New evidence review note")).toHaveValue(
      "Revised privacy note.",
    );
    expect(
      screen.queryByText("Could not add evidence review."),
    ).not.toBeInTheDocument();
  });
});
