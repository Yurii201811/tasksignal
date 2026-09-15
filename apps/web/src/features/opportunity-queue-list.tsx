import Link from "next/link";
import { ArrowRight, ChevronDown } from "lucide-react";
import { Badge, ScoreBar } from "@/components/ui";
import {
  READINESS_TONES,
  reviewStateOption,
  unresolvedSensitiveRisk,
} from "@/lib/review";
import { queueOpportunityHref, type QueueView } from "@/lib/queue-view";
import type { Opportunity } from "@/lib/types";

export function OpportunityQueueList({
  items,
  view,
  loading,
  error,
  hasOpportunities,
  hasScopeFilters,
}: {
  items: Opportunity[];
  view: QueueView;
  loading: boolean;
  error: boolean;
  hasOpportunities: boolean;
  hasScopeFilters: boolean;
}) {
  return (
    <section aria-label="Top opportunities" className="queue-results">
      <div className="queue-column-head" aria-hidden="true">
        <span>Opportunity</span>
        <span>Decision</span>
        <span>Evidence</span>
        <span>Priority</span>
      </div>
      {loading ? (
        <div role="status" className="space-y-5 py-6">
          <span className="sr-only">Loading opportunities</span>
          {[0, 1, 2].map((n) => (
            <div
              key={n}
              className="h-20 rounded-product bg-surface-muted motion-safe:animate-pulse"
            />
          ))}
        </div>
      ) : null}
      {!loading && !error && !items.length ? (
        <div className="py-12 text-center">
          <h3 className="font-semibold">
            {!hasOpportunities
              ? "No ranked opportunities yet"
              : view.q.trim()
                ? "No current opportunities match your search"
                : hasScopeFilters
                  ? "No current opportunities match these filters"
                  : "No opportunities match this decision state"}
          </h3>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
            {!hasOpportunities
              ? "Process demo data or run a research project to start with real source context."
              : "Try a broader search or clear your filters to see more of your research."}
          </p>
        </div>
      ) : null}
      {!loading && !error
        ? items.map((item) => {
            const state = reviewStateOption(item.review_state);
            const evidence = item.evidence_readiness;
            const href = queueOpportunityHref(item.id, view);
            return (
              <article key={item.id} className="queue-row">
                <div className="min-w-0">
                  <h3>
                    <Link href={href} className="queue-title">
                      {item.title}
                    </Link>
                  </h3>
                  {item.evidence_items.some(unresolvedSensitiveRisk) ? (
                    <div className="mt-2">
                      <Badge tone="red">Sensitive risk · build blocked</Badge>
                    </div>
                  ) : null}
                  <p className="mt-1.5 line-clamp-2 max-w-2xl text-sm leading-6 text-muted">
                    {item.problem_statement}
                  </p>
                  <p className="mt-2 text-xs text-muted">
                    {item.signal_count} signals <span aria-hidden>·</span>{" "}
                    {item.top_source} <span aria-hidden>·</span>{" "}
                    {item.target_user}
                  </p>
                </div>
                <div className="queue-cell">
                  <span className="queue-mobile-label">Decision</span>
                  <Badge tone={state.tone}>{state.label}</Badge>
                </div>
                <div className="queue-cell">
                  <span className="queue-mobile-label">Evidence</span>
                  <Badge tone={READINESS_TONES[evidence.level]}>
                    {evidence.level}
                  </Badge>
                  <span className="mt-2 block text-xs text-muted">
                    {evidence.reviewed_count}/{evidence.evidence_count} reviewed
                  </span>
                </div>
                <div className="queue-cell">
                  <span className="queue-mobile-label">Priority score</span>
                  <span className="text-xl font-semibold tabular-nums">
                    {Math.round(item.opportunity_score * 100)}
                    <span className="ml-1 text-xs font-normal text-muted">
                      /100
                    </span>
                  </span>
                  <Link
                    href={href}
                    className="mt-1 inline-flex min-h-11 items-center gap-1 whitespace-nowrap rounded-product text-sm font-semibold text-signal"
                  >
                    Open <ArrowRight size={14} aria-hidden />
                  </Link>
                </div>
                <details className="queue-details group">
                  <summary className="flex min-h-11 w-fit cursor-pointer list-none items-center gap-2 rounded-product text-xs font-medium text-muted hover:text-ink">
                    Evidence gaps & score details
                    <ChevronDown
                      className="h-3.5 w-3.5 motion-safe:transition-transform group-open:rotate-180"
                      aria-hidden
                    />
                  </summary>
                  <div className="grid gap-4 pb-2 text-sm sm:grid-cols-2">
                    <div>
                      <p className="font-medium">Next evidence step</p>
                      <p className="mt-1 leading-6 text-muted">
                        {evidence.gaps.length
                          ? evidence.gaps.join(" ")
                          : "Readiness checks passed. Validate the problem with potential users before building."}
                      </p>
                    </div>
                    <div>
                      <div className="mb-2 flex justify-between gap-3 text-xs text-muted">
                        <span>Feasibility</span>
                        <span>{Math.round(item.feasibility_score * 100)}%</span>
                      </div>
                      <ScoreBar
                        value={item.feasibility_score}
                        label={`${item.title} feasibility score`}
                      />
                      <p className="mt-2 text-xs text-muted">
                        Snapshot{" "}
                        {new Date(item.created_at).toLocaleDateString()}. Scores
                        prioritize research; they do not establish demand.
                      </p>
                    </div>
                  </div>
                </details>
              </article>
            );
          })
        : null}
    </section>
  );
}
