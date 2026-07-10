"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Download,
  ExternalLink,
  FileText,
  RotateCw,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  PageHeader,
  ScoreBar,
  StateMessage,
  TableShell,
} from "@/components/ui";
import { apiErrorMessage } from "@/lib/api-error";
import type { EvidenceItem, ScoreBreakdown } from "@/lib/types";
import { safeExternalUrl } from "@/lib/url";

const SCORE_ROWS = [
  { key: "frequency", label: "Frequency", weight: 0.25 },
  { key: "recency", label: "Recency", weight: 0.2 },
  { key: "pain_intensity", label: "Pain intensity", weight: 0.2 },
  { key: "task_concreteness", label: "Task concreteness", weight: 0.15 },
  { key: "buying_intent", label: "Buying intent", weight: 0.1 },
  { key: "feasibility", label: "Feasibility", weight: 0.1 },
  { key: "competition_penalty", label: "Competition penalty", weight: -0.1 },
] as const;

function scoreValue(breakdown: ScoreBreakdown, key: keyof ScoreBreakdown) {
  const value = breakdown[key];
  return typeof value === "number" ? value : 0;
}

function percent(value: number) {
  return Math.round(value * 100);
}

function evidenceSnippets(item: EvidenceItem) {
  if (item.evidence_spans?.length) {
    return item.evidence_spans.slice(0, 3);
  }
  return [`${item.body.slice(0, 240)}${item.body.length > 240 ? "..." : ""}`];
}

export function OpportunityDetail({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const [operatorToken, setOperatorToken] = useState("");
  const { data, error, isError, isLoading } = useQuery({
    queryKey: ["opportunity", id],
    queryFn: () => api.opportunity(id),
  });
  const regenerate = useMutation({
    mutationFn: () => api.regenerateOpportunity(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["opportunity", id] }),
  });
  const enhance = useMutation({
    mutationFn: () =>
      api.enhanceOpportunity(id, true, operatorToken.trim() || undefined),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["opportunity", id] }),
  });

  useEffect(() => {
    setOperatorToken(
      window.localStorage.getItem("tasksignal.operatorToken") ?? "",
    );
  }, []);

  if (isLoading) {
    return (
      <StateMessage tone="info" title="Loading opportunity and evidence">
        Fetching the score breakdown, source trail, and generated prompt state.
      </StateMessage>
    );
  }

  if (isError) {
    return (
      <StateMessage tone="danger" title="Could not load this opportunity">
        {apiErrorMessage(error)}
      </StateMessage>
    );
  }

  if (!data) {
    return (
      <StateMessage tone="warning" title="Opportunity not found">
        Process demo data from the dashboard first, then open a ranked result.
      </StateMessage>
    );
  }

  const breakdown = data.scoring_breakdown_json;
  const rankDrivers = Array.isArray(breakdown.rank_drivers)
    ? breakdown.rank_drivers
    : [];
  const commonPhrases = Array.isArray(breakdown.common_phrases)
    ? breakdown.common_phrases
    : [];
  const sourceMix = data.evidence_items.reduce<Record<string, number>>(
    (counts, item) => {
      counts[item.source] = (counts[item.source] ?? 0) + 1;
      return counts;
    },
    {},
  );
  const sourceMixLabel = Object.entries(sourceMix)
    .map(([source, count]) => `${source} ${count}`)
    .join(", ");
  const sourcesWithUrls = data.evidence_items.filter((item) =>
    Boolean(item.url),
  ).length;
  const formula = String(breakdown.score_formula ?? "");
  const hasOperatorToken = operatorToken.trim().length > 0;

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard"
        className="inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
      >
        <ArrowLeft size={15} /> Back to dashboard
      </Link>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px]">
        <PageHeader
          title={data.title}
          description={data.problem_statement}
          className="sm:flex-col sm:items-start"
          actions={
            <>
              <Link
                href={`/opportunities/${id}/prompt`}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-product bg-signal px-4 py-2 text-sm font-semibold text-[color-mix(in_srgb,var(--ts-surface)_96%,transparent)] hover:bg-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
              >
                <FileText size={16} /> View Codex Prompt
              </Link>
              <a
                href={api.taskPackExportUrl(id)}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-product border border-border bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
              >
                <Download size={16} /> Task Pack
              </a>
              <a
                href={api.evidenceExportUrl(id)}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-product border border-border bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
              >
                <Download size={16} /> Export Evidence
              </a>
              <Button
                variant="secondary"
                onClick={() => regenerate.mutate()}
                loading={regenerate.isPending}
                disabled={regenerate.isPending || enhance.isPending}
              >
                <RotateCw
                  size={16}
                  className={regenerate.isPending ? "animate-spin" : ""}
                />
                Regenerate
              </Button>
              <Button
                variant="secondary"
                onClick={() => enhance.mutate()}
                loading={enhance.isPending}
                disabled={
                  regenerate.isPending || enhance.isPending || !hasOperatorToken
                }
                title={
                  hasOperatorToken
                    ? "Enhance Prompt"
                    : "Add the local operator token in Settings first."
                }
              >
                <Sparkles
                  size={16}
                  className={enhance.isPending ? "animate-pulse" : ""}
                />
                Enhance Prompt
              </Button>
            </>
          }
        />

        <Card variant="muted" className="lg:text-right">
          <p className="text-sm font-semibold text-muted">Opportunity score</p>
          <p className="mt-2 text-4xl font-semibold tabular-nums text-signal">
            {Math.round(data.opportunity_score * 100)}
          </p>
          <p className="mt-2 text-xs leading-5 text-muted">
            Computed from evidence frequency, pain, task clarity, buying intent,
            feasibility, and competition penalty.
          </p>
        </Card>
      </div>

      {regenerate.error ? (
        <StateMessage tone="danger" title="Regeneration did not complete">
          {apiErrorMessage(regenerate.error)}
        </StateMessage>
      ) : null}
      {regenerate.data ? (
        <StateMessage tone="success" title="Opportunity regenerated">
          The score, prompt, and evidence view were refreshed from the API
          response.
        </StateMessage>
      ) : null}
      {enhance.error ? (
        <StateMessage tone="danger" title="Prompt enhancement did not complete">
          {apiErrorMessage(enhance.error)}
        </StateMessage>
      ) : null}
      {enhance.data ? (
        <StateMessage tone="success" title="Prompt enhanced">
          {enhance.data.provider} updated the build prompt with{" "}
          {enhance.data.model}.
        </StateMessage>
      ) : null}
      {!hasOperatorToken ? (
        <StateMessage
          tone="warning"
          title="Local operator token required"
          action={
            <Link
              href="/settings"
              className="inline-flex min-h-9 items-center justify-center gap-1 rounded-product border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
            >
              Settings <ArrowRight size={14} />
            </Link>
          }
        >
          Prompt enhancement is gated before it can use configured model
          credentials or local runtime capacity.
        </StateMessage>
      ) : null}

      <Card variant="muted">
        <h2 className="text-lg font-semibold text-ink">Evidence trail</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge tone="blue">{data.signal_count} signals</Badge>
          {sourceMixLabel ? (
            <Badge>Source mix: {sourceMixLabel}</Badge>
          ) : (
            <Badge>No source mix yet</Badge>
          )}
          <Badge tone="green">
            {sourcesWithUrls}/{data.evidence_items.length} with source URLs
          </Badge>
        </div>
        <p className="mt-3 text-sm leading-6 text-muted">
          Evidence excerpts come from detector spans. Author identity is omitted
          from exports; source URLs are preserved for review.
        </p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
        <Card className="space-y-5">
          <div>
            <h2 className="text-lg font-semibold text-ink">Problem review</h2>
            <p className="mt-1 text-sm text-muted">
              The summary stays close to the extracted evidence so reviewers can
              decide whether the ranking deserves attention.
            </p>
          </div>
          <Detail label="Target user" value={data.target_user} />
          <Detail label="Current workaround" value={data.current_workaround} />
          <Detail label="Suggested MVP" value={data.suggested_mvp} />
          <Detail label="Why now" value={data.why_now} />
          <Detail label="Competition notes" value={data.competition_notes} />
          {commonPhrases.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-muted">Common phrases</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {commonPhrases.map((phrase) => (
                  <Badge key={phrase}>{phrase}</Badge>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-ink">
                Scoring breakdown
              </h2>
              <p className="mt-1 text-sm text-muted">
                Raw inputs and weighted impact are shown separately so the rank
                is inspectable.
              </p>
            </div>
            <span className="text-3xl font-semibold tabular-nums text-signal">
              {Math.round(data.opportunity_score * 100)}
            </span>
          </div>

          <div className="mt-5">
            <TableShell tableClassName="min-w-[540px]">
              <thead className="border-b border-border text-xs uppercase text-muted">
                <tr>
                  <th className="py-2 pr-3">Factor</th>
                  <th className="py-2 pr-3">Raw</th>
                  <th className="py-2 pr-3">Weight</th>
                  <th className="py-2">Impact</th>
                </tr>
              </thead>
              <tbody>
                {SCORE_ROWS.map((row) => {
                  const value = scoreValue(breakdown, row.key);
                  const impact = value * row.weight * 100;
                  return (
                    <tr
                      key={row.key}
                      className="border-b border-border last:border-b-0"
                    >
                      <td className="py-3 pr-3 font-medium text-ink">
                        {row.label}
                      </td>
                      <td className="py-3 pr-3">
                        <div className="flex min-w-28 items-center gap-2">
                          <ScoreBar value={value} />
                          <span className="w-8 text-right tabular-nums text-muted">
                            {percent(value)}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 pr-3 tabular-nums text-muted">
                        {row.weight > 0 ? "+" : ""}
                        {Math.round(row.weight * 100)}%
                      </td>
                      <td
                        className={
                          impact < 0
                            ? "py-3 tabular-nums text-danger"
                            : "py-3 tabular-nums text-ink"
                        }
                      >
                        {impact.toFixed(1)} pts
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </TableShell>
          </div>

          {rankDrivers.length > 0 && (
            <div className="mt-5 border-t border-border pt-4">
              <p className="text-sm font-semibold text-ink">Top rank drivers</p>
              <ul className="mt-2 grid gap-2 text-sm text-muted">
                {rankDrivers.map((driver) => (
                  <li key={driver} className="flex gap-2">
                    <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-signal" />
                    <span>{driver}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {formula ? (
            <div className="mt-5 border-t border-border pt-4">
              <p className="text-sm font-semibold text-ink">Formula</p>
              <p className="mt-2 break-words font-mono text-xs leading-6 text-muted">
                {formula}
              </p>
            </div>
          ) : null}
          {breakdown.explanation ? (
            <p className="mt-4 text-sm leading-6 text-muted">
              {String(breakdown.explanation)}
            </p>
          ) : null}
        </Card>
      </div>

      <section className="space-y-4">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
          <div>
            <h2 className="text-lg font-semibold text-ink">Evidence items</h2>
            <p className="mt-1 text-sm text-muted">
              Source attribution, signal type, and mini scores stay visible for
              each excerpt.
            </p>
          </div>
          <Badge>{data.evidence_items.length} evidence records</Badge>
        </div>

        <div className="grid gap-4">
          {data.evidence_items.length === 0 ? (
            <Card variant="muted">
              <p className="text-sm leading-6 text-muted">
                No evidence items were returned for this opportunity. Regenerate
                after processing demo data.
              </p>
            </Card>
          ) : null}
          {data.evidence_items.map((item) => {
            const sourceUrl = safeExternalUrl(item.url);
            return (
              <article
                key={item.id}
                className="rounded-product border border-border bg-surface p-4 shadow-soft"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <Badge tone="blue">{item.source}</Badge>
                    <Badge tone={item.signal_type === null ? "slate" : "green"}>
                      {item.signal_type === null
                        ? "Not classified"
                        : item.signal_type.replace("_", " ")}
                    </Badge>
                  </div>
                  {sourceUrl ? (
                    <a
                      href={sourceUrl}
                      className="inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
                      rel="noreferrer"
                      target="_blank"
                    >
                      Source <ExternalLink size={14} />
                    </a>
                  ) : null}
                </div>
                <h3 className="mt-3 break-words font-semibold text-ink">
                  {item.title}
                </h3>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  <MiniScore label="Pain" value={item.pain_score} />
                  <MiniScore
                    label="Task"
                    value={item.task_concreteness_score}
                  />
                  <MiniScore label="Buying" value={item.buying_intent_score} />
                </div>
                <div className="mt-4 grid gap-2">
                  {evidenceSnippets(item).map((snippet) => (
                    <blockquote
                      key={snippet}
                      className="rounded-product bg-surface-muted px-4 py-3 text-sm leading-6 text-muted"
                    >
                      <span
                        className="mr-2 font-semibold text-signal"
                        aria-hidden
                      >
                        &quot;
                      </span>
                      <span className="break-words">{snippet}</span>
                    </blockquote>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function MiniScore({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs font-semibold text-muted">
        <span>{label}</span>
        <span>{value === null ? "Not measured" : percent(value)}</span>
      </div>
      {value === null ? null : <ScoreBar value={value} />}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm font-semibold text-muted">{label}</p>
      <p className="mt-1 break-words leading-6 text-ink">{value}</p>
    </div>
  );
}
