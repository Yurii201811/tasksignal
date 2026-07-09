import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../src/lib/api";

describe("decision workbench API", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("encodes an optional opportunity state filter", async () => {
    const fetchMock = vi.fn(async () => Response.json([]));
    vi.stubGlobal("fetch", fetchMock);

    await api.opportunities("needs_more_evidence");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/opportunities?review_state=needs_more_evidence",
      expect.any(Object),
    );
  });

  it("sends the exact opportunity review patch", async () => {
    const fetchMock = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetchMock);

    await api.updateOpportunityReview("opportunity-1", {
      review_state: "promising",
      review_note: "Validate with maintainers.",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/opportunities/opportunity-1/review",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          review_state: "promising",
          review_note: "Validate with maintainers.",
        }),
      }),
    );
  });

  it("writes evidence reviews and reads history and evaluation", async () => {
    const fetchMock = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetchMock);

    await api.createEvidenceReview({
      item_id: "item-1",
      label: "true_signal",
      user_note: null,
    });
    await api.itemReviewHistory("item-1");
    await api.evaluation();

    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      "http://localhost:8000/api/labels",
      "http://localhost:8000/api/items/item-1/labels",
      "http://localhost:8000/api/evaluation",
    ]);
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          item_id: "item-1",
          label: "true_signal",
          user_note: null,
        }),
      }),
    );
  });
});
