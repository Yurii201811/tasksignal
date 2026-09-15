import { describe, expect, it } from "vitest";
import {
  DEFAULT_QUEUE_VIEW,
  parseQueueView,
  queueHref,
  queueOpportunityHref,
  selectQueueItems,
} from "../src/lib/queue-view";
import type { Opportunity } from "../src/lib/types";

const rows = [
  {
    id: "older",
    title: "CI repair",
    problem_statement: "Slow manual checks",
    target_user: "Maintainers",
    top_source: "github",
    evidence_items: [{ source: "hackernews" }],
    opportunity_score: 0.8,
    created_at: "2026-09-01T10:00:00Z",
    evidence_readiness: { level: "medium" },
  },
  {
    id: "newer",
    title: "Reports",
    problem_statement: "Weekly export",
    target_user: "Operators",
    top_source: "reddit",
    evidence_items: [],
    opportunity_score: 0.5,
    created_at: "2026-09-02T10:00:00Z",
    evidence_readiness: { level: "strong" },
  },
] as Opportunity[];

describe("queue views", () => {
  it("round trips a scoped view and retains it on the opportunity link", () => {
    const view = {
      ...DEFAULT_QUEUE_VIEW,
      q: "CI & reviews",
      project: "project/one",
      source: "github",
      review: "promising" as const,
      readiness: "medium" as const,
      age: "30" as const,
      sort: "readiness" as const,
    };
    const url = new URL(queueHref(view), "http://localhost");
    expect(parseQueueView(url.searchParams)).toEqual(view);
    const detail = new URL(queueOpportunityHref("snapshot/1", view), url);
    expect(detail.pathname).toBe("/opportunities/snapshot%2F1");
    expect(
      parseQueueView(new URLSearchParams(detail.searchParams.get("queue")!)),
    ).toEqual(view);
    expect(queueHref(DEFAULT_QUEUE_VIEW)).toBe("/dashboard");
    expect(queueOpportunityHref("one", DEFAULT_QUEUE_VIEW)).toBe(
      "/opportunities/one?queue=",
    );
  });

  it("drops unknown fields and validates enums rather than using redirect input", () => {
    const parsed = parseQueueView(
      new URLSearchParams(
        "sort=bogus&review=admin&age=-1&readiness=ready&redirect=https://example.com",
      ),
    );
    expect(parsed).toEqual(DEFAULT_QUEUE_VIEW);
    expect(queueHref(parsed)).toBe("/dashboard");
    expect(
      parseQueueView(new URLSearchParams({ q: "x".repeat(500) })).q,
    ).toHaveLength(300);
  });

  it("searches evidence sources and sorts without changing the server rows", () => {
    expect(
      selectQueueItems(rows, { q: "HACKERNEWS", sort: "score" }).map(
        (row) => row.id,
      ),
    ).toEqual(["older"]);
    expect(
      selectQueueItems(rows, { q: "", sort: "newest" }).map((row) => row.id),
    ).toEqual(["newer", "older"]);
    expect(
      selectQueueItems(rows, { q: "", sort: "readiness" }).map((row) => row.id),
    ).toEqual(["newer", "older"]);
    expect(rows.map((row) => row.id)).toEqual(["older", "newer"]);
  });
});
