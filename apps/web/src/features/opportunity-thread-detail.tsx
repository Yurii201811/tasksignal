"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, GitBranch, Scissors, Save } from "lucide-react";
import { api } from "@/lib/api";
import type { ReviewState } from "@/lib/types";
import {
  READINESS_TONES,
  REVIEW_STATE_OPTIONS,
  reviewStateOption,
} from "@/lib/review";
import { BuildStudio } from "@/features/build-studio";
import { matchMethodLabel } from "@/features/opportunity-threads";
import {
  Badge,
  Button,
  Card,
  PageHeader,
  Select,
  StateMessage,
  Textarea,
} from "@/components/ui";

function percent(value: number | null | undefined) {
  return value === null || value === undefined
    ? "Not scored"
    : `${Math.round(value * 100)}%`;
}

function errorMessage(error: unknown) {
  if (!(error instanceof Error)) return "The request failed.";
  try {
    const detail = JSON.parse(error.message)?.detail;
    return typeof detail === "string" ? detail : error.message;
  } catch {
    return error.message;
  }
}

export function OpportunityThreadDetail({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [reviewState, setReviewState] = useState<ReviewState>("new");
  const [reviewNote, setReviewNote] = useState("");
  const thread = useQuery({
    queryKey: ["opportunity-thread", id],
    queryFn: () => api.opportunityThread(id),
  });
  const updateDecision = useMutation({
    mutationFn: () =>
      api.updateOpportunityThreadDecision(id, {
        review_state: reviewState,
        review_note: reviewNote.trim() || null,
        expected_version: thread.data?.version ?? 0,
      }),
    onSuccess: (next) => {
      queryClient.setQueryData(["opportunity-thread", id], next);
      queryClient.invalidateQueries({ queryKey: ["opportunity-threads"] });
    },
  });
  const detach = useMutation({
    mutationFn: (snapshotId: string) =>
      api.detachOpportunitySnapshot(id, snapshotId, thread.data?.version ?? 0),
    onSuccess: (result) => {
      queryClient.setQueryData(
        ["opportunity-thread", id],
        result.source_thread,
      );
      queryClient.invalidateQueries({ queryKey: ["opportunity-threads"] });
    },
  });

  useEffect(() => {
    if (!thread.data) return;
    setReviewState(thread.data.review_state);
    setReviewNote(thread.data.review_note ?? "");
  }, [thread.data]);

  if (thread.isLoading) {
    return (
      <StateMessage tone="info" title="Loading opportunity thread">
        Reading snapshots, matching metadata, and decision history.
      </StateMessage>
    );
  }
  if (thread.error || !thread.data) {
    return (
      <StateMessage tone="danger" title="Could not load opportunity thread">
        {errorMessage(thread.error)}
      </StateMessage>
    );
  }

  const data = thread.data;
  const current = data.current_snapshot;
  const state = reviewStateOption(data.review_state);

  return (
    <div className="space-y-6">
      <PageHeader
        title={current?.title ?? "Opportunity thread"}
        description={
          current?.problem_statement ?? "This thread has no current snapshot."
        }
        actions={
          <Link
            href="/threads"
            className="inline-flex min-h-11 items-center gap-2 rounded-product border border-border-strong bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
          >
            <ArrowLeft size={16} aria-hidden /> Threads
          </Link>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <div className="flex flex-wrap gap-2">
            <Badge tone={state.tone}>{state.label}</Badge>
            <Badge
              tone={data.lineage_status === "complete" ? "green" : "slate"}
            >
              {data.lineage_status} lineage
            </Badge>
            <Badge>{data.snapshot_count} snapshots</Badge>
            {current ? (
              <Badge tone={READINESS_TONES[current.evidence_readiness.level]}>
                {current.evidence_readiness.level} readiness
              </Badge>
            ) : null}
          </div>
          <h2 className="mt-4 text-lg font-semibold text-ink">
            Automatic match record
          </h2>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="border-t border-border pt-3">
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                Match method
              </dt>
              <dd className="mt-1 font-semibold text-ink">
                {matchMethodLabel(current?.match_method)}
              </dd>
            </div>
            <div className="border-t border-border pt-3">
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                Confidence
              </dt>
              <dd className="mt-1 font-semibold tabular-nums text-ink">
                {percent(current?.match_confidence)}
              </dd>
            </div>
            <div className="border-t border-border pt-3">
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                Runner-up margin
              </dt>
              <dd className="mt-1 font-semibold tabular-nums text-ink">
                {percent(current?.match_margin)}
              </dd>
            </div>
            <div className="border-t border-border pt-3">
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                Embedding identity
              </dt>
              <dd className="mt-1 break-words text-sm text-ink">
                {current?.embedding_backend && current?.embedding_model
                  ? `${current.embedding_backend} / ${current.embedding_model}`
                  : "Not recorded"}
              </dd>
            </div>
          </dl>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-ink">Human decision</h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            This state persists across future matched snapshots. Notes stay
            local and out of packets.
          </p>
          <label className="mt-4 block">
            <span className="text-sm font-semibold text-muted">
              Review state
            </span>
            <Select
              className="mt-2"
              value={reviewState}
              onChange={(event) =>
                setReviewState(event.target.value as ReviewState)
              }
            >
              {REVIEW_STATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </label>
          <label className="mt-4 block">
            <span className="text-sm font-semibold text-muted">
              Local review note
            </span>
            <Textarea
              className="mt-2"
              value={reviewNote}
              onChange={(event) => setReviewNote(event.target.value)}
              maxLength={1000}
            />
          </label>
          <Button
            className="mt-4"
            loading={updateDecision.isPending}
            onClick={() => updateDecision.mutate()}
          >
            <Save size={16} aria-hidden /> Save thread decision
          </Button>
          {updateDecision.error ? (
            <StateMessage
              className="mt-4"
              tone="danger"
              title="Decision was not saved"
            >
              {errorMessage(updateDecision.error)}
            </StateMessage>
          ) : null}
        </Card>
      </div>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-ink">Snapshot history</h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              Matching never rewrites a snapshot. A human may detach an
              incorrect historical match.
            </p>
          </div>
          <Badge tone="blue">Human correction only</Badge>
        </div>
        <div className="mt-4 divide-y divide-border">
          {data.snapshots.map((snapshot) => {
            const isCurrent = snapshot.id === data.current_snapshot?.id;
            return (
              <article
                key={snapshot.id}
                className="grid gap-4 py-4 first:pt-0 last:pb-0 lg:grid-cols-[minmax(0,1fr)_220px]"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={isCurrent ? "green" : "slate"}>
                      {isCurrent ? "Current" : "Historical"}
                    </Badge>
                    <Badge>{matchMethodLabel(snapshot.match_method)}</Badge>
                    <Badge>
                      {percent(snapshot.match_confidence)} confidence
                    </Badge>
                  </div>
                  <h3 className="mt-2 break-words font-semibold text-ink">
                    {snapshot.title}
                  </h3>
                  <p className="mt-1 text-sm text-muted">
                    Observed {new Date(snapshot.created_at).toLocaleString()} ·{" "}
                    {snapshot.signal_count} signals
                  </p>
                </div>
                {!isCurrent && data.snapshots.length > 1 ? (
                  <Button
                    variant="secondary"
                    loading={
                      detach.isPending && detach.variables === snapshot.id
                    }
                    disabled={detach.isPending}
                    onClick={() => detach.mutate(snapshot.id)}
                  >
                    <Scissors size={16} aria-hidden /> Detach snapshot into a
                    new thread
                  </Button>
                ) : null}
              </article>
            );
          })}
        </div>
        {detach.error ? (
          <StateMessage
            className="mt-4"
            tone="danger"
            title="Snapshot was not detached"
          >
            {errorMessage(detach.error)}
          </StateMessage>
        ) : null}
      </Card>

      <BuildStudio thread={data} />

      {data.decision_history.length > 0 ? (
        <Card>
          <h2 className="text-lg font-semibold text-ink">Decision history</h2>
          <ol className="mt-4 grid gap-3">
            {data.decision_history.map((event) => (
              <li
                key={event.id}
                className="flex gap-3 border-t border-border pt-3 text-sm"
              >
                <GitBranch
                  className="mt-1 h-4 w-4 shrink-0 text-signal"
                  aria-hidden
                />
                <div>
                  <p className="font-semibold text-ink">
                    {event.event_type.replaceAll("_", " ")}
                  </p>
                  <p className="mt-1 text-muted">
                    {event.actor_type} ·{" "}
                    {new Date(event.created_at).toLocaleString()}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      ) : null}
    </div>
  );
}
