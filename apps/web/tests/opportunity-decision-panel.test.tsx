import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OpportunityDecisionPanel } from "../src/features/opportunity-decision-panel";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: { updateOpportunityReview: vi.fn() },
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

describe("OpportunityDecisionPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the exact decision value and label options", () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <OpportunityDecisionPanel
          opportunityId="opportunity-1"
          reviewState="new"
          reviewNote={null}
          decisionUpdatedAt={null}
        />
      </QueryClientProvider>,
    );

    const select = screen.getByLabelText("Decision state") as HTMLSelectElement;
    expect(
      Array.from(select.options, (option) => [option.value, option.label]),
    ).toEqual([
      ["new", "New"],
      ["needs_more_evidence", "Needs more evidence"],
      ["promising", "Promising"],
      ["rejected", "Rejected"],
      ["duplicate", "Duplicate"],
      ["build_candidate", "Build candidate"],
    ]);
  });

  it("saves an exact decision payload then invalidates detail and list", async () => {
    vi.mocked(api.updateOpportunityReview).mockResolvedValue({} as never);
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        <OpportunityDecisionPanel
          opportunityId="opportunity-1"
          reviewState="new"
          reviewNote={null}
          decisionUpdatedAt={null}
        />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText("Decision state"), {
      target: { value: "promising" },
    });
    fireEvent.change(screen.getByLabelText("Local review note"), {
      target: { value: "Validate with maintainers." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save decision" }));

    await waitFor(() => {
      expect(api.updateOpportunityReview).toHaveBeenCalledWith("opportunity-1", {
        review_state: "promising",
        review_note: "Validate with maintainers.",
      });
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ["opportunity", "opportunity-1"],
      });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["opportunities"] });
    });
    expect(await screen.findByText("Decision saved")).toBeInTheDocument();
  });

  it("keeps a non-default failed draft separate from confirmed server state", async () => {
    const request = deferred<never>();
    vi.mocked(api.updateOpportunityReview).mockReturnValue(request.promise);
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        <OpportunityDecisionPanel
          opportunityId="opportunity-1"
          reviewState="new"
          reviewNote={null}
          decisionUpdatedAt={null}
        />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Decision state"), {
      target: { value: "build_candidate" },
    });
    fireEvent.change(screen.getByLabelText("Local review note"), {
      target: { value: "Keep this draft" },
    });
    expect(screen.getByLabelText("Local review note")).toHaveAttribute(
      "maxlength",
      "1000",
    );
    fireEvent.click(screen.getByRole("button", { name: "Save decision" }));

    await waitFor(() => {
      expect(api.updateOpportunityReview).toHaveBeenCalledWith(
        "opportunity-1",
        {
          review_state: "build_candidate",
          review_note: "Keep this draft",
        },
      );
    });
    expect(screen.getByText("Confirmed: New")).toBeInTheDocument();
    expect(screen.getByLabelText("Decision state")).toHaveValue(
      "build_candidate",
    );
    expect(screen.getByDisplayValue("Keep this draft")).toBeInTheDocument();
    expect(screen.queryByText("Decision saved")).not.toBeInTheDocument();
    expect(invalidate).not.toHaveBeenCalled();

    request.reject(
      new Error(JSON.stringify({ detail: "Could not save decision." })),
    );

    expect(
      await screen.findByText("Could not save decision."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Decision state")).toHaveValue(
      "build_candidate",
    );
    expect(screen.getByDisplayValue("Keep this draft")).toBeInTheDocument();
    expect(screen.getByText("Confirmed: New")).toBeInTheDocument();
    expect(screen.queryByText("Decision saved")).not.toBeInTheDocument();
    expect(invalidate).not.toHaveBeenCalled();
  });
});
