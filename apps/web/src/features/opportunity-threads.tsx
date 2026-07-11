"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, GitBranch } from "lucide-react";
import { api } from "@/lib/api";
import type { ReviewState } from "@/lib/types";
import {
  READINESS_TONES,
  REVIEW_STATE_OPTIONS,
  reviewStateOption,
} from "@/lib/review";
import {
  Badge,
  Card,
  PageHeader,
  Select,
  StateMessage,
  TableShell,
} from "@/components/ui";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request failed.";
}

export function matchMethodLabel(method: string | null | undefined) {
  if (!method) return "initial snapshot";
  return method.replaceAll("_", " ");
}

export function OpportunityThreads() {
  const [reviewState, setReviewState] = useState<"all" | ReviewState>("all");
  const filter = reviewState === "all" ? undefined : reviewState;
  const threads = useQuery({
    queryKey: ["opportunity-threads", { reviewState: filter }],
    queryFn: () =>
      api.opportunityThreads(filter ? { reviewState: filter } : undefined),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Opportunity threads"
        description="Follow a durable opportunity across runs, inspect automatic match evidence, and keep human decisions attached to the thread."
      />

      <Card variant="muted">
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_260px] sm:items-end">
          <div>
            <h2 className="font-semibold text-ink">Server-side review queue</h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              The API applies the decision filter before returning thread
              snapshots.
            </p>
          </div>
          <label>
            <span className="text-sm font-semibold text-muted">
              Review state
            </span>
            <Select
              className="mt-2"
              aria-label="Review state"
              value={reviewState}
              onChange={(event) =>
                setReviewState(event.target.value as "all" | ReviewState)
              }
            >
              <option value="all">All decision states</option>
              {REVIEW_STATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </label>
        </div>
      </Card>

      {threads.error ? (
        <StateMessage tone="danger" title="Could not load opportunity threads">
          {errorMessage(threads.error)}
        </StateMessage>
      ) : null}
      {threads.isLoading ? (
        <StateMessage tone="info" title="Loading opportunity threads">
          Reading current snapshots and their lineage metadata.
        </StateMessage>
      ) : null}
      {!threads.isLoading && (threads.data ?? []).length === 0 ? (
        <StateMessage tone="warning" title="No threads match this review state">
          Run a research project or choose another server-side filter.
        </StateMessage>
      ) : null}

      {(threads.data ?? []).length > 0 ? (
        <Card>
          <TableShell
            label="Opportunity threads"
            caption="Durable opportunity threads with decision and matching metadata"
            tableClassName="min-w-[920px]"
          >
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="py-3 pr-4">Current opportunity</th>
                <th className="py-3 pr-4">Decision</th>
                <th className="py-3 pr-4">Readiness</th>
                <th className="py-3 pr-4">Latest match</th>
                <th className="py-3 pr-4">Snapshots</th>
                <th className="py-3 text-right">Open</th>
              </tr>
            </thead>
            <tbody>
              {(threads.data ?? []).map((thread) => {
                const snapshot = thread.current_snapshot;
                const state = reviewStateOption(thread.review_state);
                return (
                  <tr
                    key={thread.id}
                    className="border-b border-border last:border-0"
                  >
                    <td className="max-w-md py-4 pr-4 align-top">
                      <div className="flex items-start gap-3">
                        <GitBranch
                          className="mt-1 h-4 w-4 shrink-0 text-signal"
                          aria-hidden
                        />
                        <div className="min-w-0">
                          <p className="break-words font-semibold text-ink">
                            {snapshot?.title ??
                              "Thread without a current snapshot"}
                          </p>
                          <p className="mt-1 line-clamp-2 text-sm leading-6 text-muted">
                            {snapshot?.problem_statement ??
                              "Lineage requires inspection."}
                          </p>
                          <Badge
                            tone={
                              thread.lineage_status === "complete"
                                ? "green"
                                : "slate"
                            }
                          >
                            {thread.lineage_status} lineage
                          </Badge>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 pr-4 align-top">
                      <Badge tone={state.tone}>{state.label}</Badge>
                    </td>
                    <td className="py-4 pr-4 align-top">
                      {snapshot ? (
                        <Badge
                          tone={
                            READINESS_TONES[snapshot.evidence_readiness.level]
                          }
                        >
                          {snapshot.evidence_readiness.level}
                        </Badge>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="py-4 pr-4 align-top text-sm text-muted">
                      <p>{matchMethodLabel(snapshot?.match_method)}</p>
                      <p className="mt-1 font-semibold tabular-nums text-ink">
                        {snapshot?.match_confidence === null ||
                        snapshot?.match_confidence === undefined
                          ? "No confidence score"
                          : `${Math.round(snapshot.match_confidence * 100)}% confidence`}
                      </p>
                    </td>
                    <td className="py-4 pr-4 align-top tabular-nums text-muted">
                      {thread.snapshot_count}
                    </td>
                    <td className="py-4 text-right align-top">
                      <Link
                        href={`/threads/${thread.id}`}
                        className="inline-flex min-h-11 items-center gap-2 rounded-product px-3 py-2 text-sm font-semibold text-signal hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
                      >
                        Inspect thread <ArrowRight size={15} aria-hidden />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </TableShell>
        </Card>
      ) : null}
    </div>
  );
}
