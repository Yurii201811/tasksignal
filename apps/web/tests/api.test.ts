import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../src/lib/api";

function installLocalStorageMock() {
  const store: Record<string, string> = {};
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: vi.fn((key: string) => store[key] ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = value;
      }),
      removeItem: vi.fn((key: string) => {
        delete store[key];
      }),
      clear: vi.fn(() => {
        for (const key of Object.keys(store)) delete store[key];
      }),
    },
  });
}

describe("decision workbench API", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    installLocalStorageMock();
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

  it("adds the saved operator token to reads and writes", async () => {
    const fetchMock = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetchMock);
    window.localStorage.setItem(
      "tasksignal.operatorToken",
      "hosted-operator-token",
    );

    await api.updateOpportunityReview("opportunity-1", {
      review_state: "promising",
      review_note: null,
    });
    await api.createEvidenceReview({
      item_id: "item-1",
      label: "true_signal",
      user_note: null,
    });
    await api.opportunities();

    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Operator-Scan-Token": "hosted-operator-token",
        }),
      }),
    );
    expect(fetchMock.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Operator-Scan-Token": "hosted-operator-token",
        }),
      }),
    );
    expect(fetchMock.mock.calls[2][1]).toEqual(
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Operator-Scan-Token": "hosted-operator-token",
        }),
      }),
    );
  });

  it("omits the operator token when the browser has not been unlocked", async () => {
    const fetchMock = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetchMock);

    await api.opportunities();

    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        headers: expect.not.objectContaining({
          "X-Operator-Scan-Token": expect.anything(),
        }),
      }),
    );
  });

  it("lets an explicit operator token override the saved token", async () => {
    const fetchMock = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetchMock);
    window.localStorage.setItem("tasksignal.operatorToken", "saved-token");

    await api.enhanceOpportunity("opportunity-1", true, "explicit-token");

    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Operator-Scan-Token": "explicit-token",
        }),
      }),
    );
  });

  it("downloads protected exports with the saved token and no token in the URL", async () => {
    const fetchMock = vi.fn(async () => new Response("# Task pack"));
    vi.stubGlobal("fetch", fetchMock);
    window.localStorage.setItem("tasksignal.operatorToken", "saved-token");
    const createObjectURL = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:protected-export");
    const revokeObjectURL = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    await api.downloadTaskPack("opportunity-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/opportunities/opportunity-1/task-pack.md",
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Operator-Scan-Token": "saved-token",
        }),
      }),
    );
    expect(String(fetchMock.mock.calls[0][0])).not.toContain("saved-token");
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:protected-export");
  });
});
