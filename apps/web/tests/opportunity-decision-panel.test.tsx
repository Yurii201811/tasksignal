import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OpportunityDecisionPanel } from "../src/features/opportunity-decision-panel";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: { updateOpportunityReview: vi.fn() },
}));

describe("OpportunityDecisionPanel", () => {
  beforeEach(() => vi.clearAllMocks());

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

  it("keeps confirmed state and draft visible after a failed save", async () => {
    vi.mocked(api.updateOpportunityReview).mockRejectedValue(
      new Error(JSON.stringify({ detail: "Could not save decision." })),
    );
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
    fireEvent.change(screen.getByLabelText("Local review note"), {
      target: { value: "Keep this draft" },
    });
    expect(screen.getByLabelText("Local review note")).toHaveAttribute(
      "maxlength",
      "1000",
    );
    fireEvent.click(screen.getByRole("button", { name: "Save decision" }));

    expect(
      await screen.findByText("Could not save decision."),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("Keep this draft")).toBeInTheDocument();
    expect(screen.getByText("Confirmed: New")).toBeInTheDocument();
    expect(screen.queryByText("Decision saved")).not.toBeInTheDocument();
  });
});
