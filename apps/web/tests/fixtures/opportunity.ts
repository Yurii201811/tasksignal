import type { Opportunity } from "../../src/lib/types";

export function queueOpportunity(
  overrides: Partial<Opportunity> = {},
): Opportunity {
  return {
    id: "one",
    cluster_id: "cluster-one",
    title: "CI repair",
    problem_statement: "Slow manual checks",
    target_user: "Maintainers",
    current_workaround: "Manual review",
    suggested_mvp: "A focused repair tool",
    why_now: "Repeated workflow problems",
    competition_notes: "Keep scope narrow",
    top_source: "github",
    evidence_items: [],
    opportunity_score: 0.8,
    feasibility_score: 0.7,
    scoring_breakdown_json: {},
    generated_prompt: "Review the source evidence.",
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
    review_state: "new",
    review_note: null,
    decision_updated_at: null,
    signal_count: 0,
    evidence_readiness: {
      level: "medium",
      evidence_count: 0,
      source_count: 0,
      safe_url_count: 0,
      reviewed_count: 0,
      source_url_coverage: 0,
      human_review_coverage: 0,
      checks: {
        enough_evidence: false,
        source_diversity: false,
        source_url_coverage: false,
        human_review_coverage: false,
      },
      passed_checks: [],
      gaps: ["Collect evidence"],
    },
    ...overrides,
  };
}
