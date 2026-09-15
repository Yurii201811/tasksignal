import type { EvidenceReadinessLevel, Opportunity, ReviewState } from "./types";
import { REVIEW_STATE_OPTIONS } from "./review";

export type QueueSort = "score" | "newest" | "readiness";
export type QueueView = {
  q: string;
  sort: QueueSort;
  review: ReviewState | "all";
  project: string;
  source: string;
  readiness: EvidenceReadinessLevel | "all";
  age: "all" | "7" | "30" | "90";
};

export const DEFAULT_QUEUE_VIEW: QueueView = {
  q: "",
  sort: "score",
  review: "all",
  project: "all",
  source: "all",
  readiness: "all",
  age: "all",
};

function choice<T extends string>(
  value: string | null,
  values: readonly T[],
  fallback: T,
): T {
  return values.includes(value as T) ? (value as T) : fallback;
}

export function parseQueueView(params: URLSearchParams): QueueView {
  return {
    q: (params.get("q") ?? "").slice(0, 300),
    sort: choice(params.get("sort"), ["score", "newest", "readiness"], "score"),
    review: choice(
      params.get("review"),
      ["all", ...REVIEW_STATE_OPTIONS.map((option) => option.value)],
      "all",
    ),
    project: params.get("project")?.slice(0, 200) || "all",
    source: params.get("source")?.slice(0, 200) || "all",
    readiness: choice(
      params.get("readiness"),
      ["all", "weak", "medium", "strong"],
      "all",
    ),
    age: choice(params.get("age"), ["all", "7", "30", "90"], "all"),
  };
}

export function queueSearchParams(view: QueueView): string {
  const params = new URLSearchParams();
  for (const key of Object.keys(DEFAULT_QUEUE_VIEW) as (keyof QueueView)[]) {
    if (view[key] !== DEFAULT_QUEUE_VIEW[key]) params.set(key, view[key]);
  }
  return params.toString();
}

export function queueHref(view: QueueView): string {
  const query = queueSearchParams(view);
  return `/dashboard${query ? `?${query}` : ""}`;
}

export function queueOpportunityHref(id: string, view: QueueView): string {
  const query = queueSearchParams(view);
  return `/opportunities/${encodeURIComponent(id)}?queue=${encodeURIComponent(query)}`;
}

export function selectQueueItems(
  items: Opportunity[],
  view: Pick<QueueView, "q" | "sort">,
): Opportunity[] {
  const query = view.q.trim().toLocaleLowerCase();
  const rank = { weak: 0, medium: 1, strong: 2 };
  return items
    .filter(
      (item) =>
        !query ||
        [
          item.title,
          item.problem_statement,
          item.target_user,
          item.top_source,
          ...item.evidence_items.map((evidence) => evidence.source),
        ].some((value) => value.toLocaleLowerCase().includes(query)),
    )
    .sort((left, right) => {
      if (view.sort === "newest")
        return (
          Date.parse(right.created_at) - Date.parse(left.created_at) ||
          left.id.localeCompare(right.id)
        );
      if (view.sort === "readiness") {
        const difference =
          rank[right.evidence_readiness.level] -
          rank[left.evidence_readiness.level];
        if (difference) return difference;
      }
      return (
        right.opportunity_score - left.opportunity_score ||
        left.id.localeCompare(right.id)
      );
    });
}
