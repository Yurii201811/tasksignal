"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ExternalLink, FileText, RotateCw } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, ScoreBar } from "@/components/ui";
import type { EvidenceItem, ScoreBreakdown } from "@/lib/types";

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

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request failed.";
}

export function OpportunityDetail({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const { data, error, isError, isLoading } = useQuery({
    queryKey: ["opportunity", id],
    queryFn: () => api.opportunity(id),
  });
  const regenerate = useMutation({
    mutationFn: () => api.regenerateOpportunity(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["opportunity", id] }),
  });

  if (isLoading) return <Card>Loading opportunity and evidence...</Card>;
  if (isError)
    return <Card>Could not load this opportunity: {errorMessage(error)}</Card>;
  if (!data)
    return (
      <Card>
        Opportunity not found. Process demo data from the dashboard first.
      </Card>
    );

  const breakdown = data.scoring_breakdown_json;
  const rankDrivers = Array.isArray(breakdown.rank_drivers)
    ? breakdown.rank_drivers
    : [];
  const commonPhrases = Array.isArray(breakdown.common_phrases)
    ? breakdown.common_phrases
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
        <div>
          <Link href="/dashboard" className="text-sm font-semibold text-signal">
            Back to dashboard
          </Link>
          <h1 className="mt-3 max-w-4xl text-3xl font-semibold leading-tight text-ink">
            {data.title}
          </h1>
          <p className="mt-3 max-w-4xl text-slate-600">
            {data.problem_statement}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/opportunities/${id}/prompt`}
            className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white"
          >
            <FileText size={16} /> View Codex Prompt
          </Link>
          <a
            href={api.exportUrl(id)}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink"
          >
            <Download size={16} /> Export Markdown
          </a>
          <button
            onClick={() => regenerate.mutate()}
            disabled={regenerate.isPending}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink disabled:cursor-wait disabled:opacity-70"
          >
            <RotateCw
              size={16}
              className={regenerate.isPending ? "animate-spin" : ""}
            />{" "}
            Regenerate
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="space-y-5">
          <Detail label="Problem statement" value={data.problem_statement} />
          <Detail label="Target user" value={data.target_user} />
          <Detail label="Current workaround" value={data.current_workaround} />
          <Detail label="Suggested MVP" value={data.suggested_mvp} />
          <Detail label="Why now" value={data.why_now} />
          <Detail label="Competition notes" value={data.competition_notes} />
          {commonPhrases.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-slate-500">
                Common phrases
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {commonPhrases.map((phrase) => (
                  <Badge key={phrase}>{phrase}</Badge>
                ))}
              </div>
            </div>
          )}
        </Card>
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-ink">
              Scoring breakdown
            </h2>
            <span className="text-3xl font-semibold text-signal">
              {Math.round(data.opportunity_score * 100)}
            </span>
          </div>
          <div className="mt-5 space-y-4">
            {SCORE_ROWS.map((row) => {
              const value = scoreValue(breakdown, row.key);
              const impact = value * row.weight * 100;
              return (
                <div key={row.key}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="font-medium text-slate-600">
                      {row.label}
                    </span>
                    <span className="text-right">
                      {percent(value)} raw /{" "}
                      <span
                        className={
                          impact < 0 ? "text-red-700" : "text-slate-700"
                        }
                      >
                        {impact.toFixed(1)} pts
                      </span>
                    </span>
                  </div>
                  <ScoreBar value={value} />
                </div>
              );
            })}
          </div>
          {rankDrivers.length > 0 && (
            <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-sm font-semibold text-ink">Top rank drivers</p>
              <ul className="mt-2 space-y-1 text-sm text-slate-600">
                {rankDrivers.map((driver) => (
                  <li key={driver}>{driver}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-4 text-sm text-slate-600">
            {String(breakdown.explanation ?? "")}
          </p>
        </Card>
      </div>

      <Card>
        <h2 className="text-lg font-semibold text-ink">Evidence items</h2>
        <div className="mt-4 grid gap-4">
          {data.evidence_items.map((item) => (
            <article
              key={item.id}
              className="rounded-lg border border-slate-200 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="blue">{item.source}</Badge>
                  <Badge tone="green">
                    {item.signal_type?.replace("_", " ")}
                  </Badge>
                </div>
                {item.url && (
                  <a
                    href={item.url}
                    className="inline-flex items-center gap-1 text-sm font-semibold text-signal"
                    rel="noreferrer"
                    target="_blank"
                  >
                    Source <ExternalLink size={14} />
                  </a>
                )}
              </div>
              <h3 className="mt-3 font-semibold text-ink">{item.title}</h3>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <MiniScore label="Pain" value={item.pain_score} />
                <MiniScore label="Task" value={item.task_concreteness_score} />
                <MiniScore label="Buying" value={item.buying_intent_score} />
              </div>
              <div className="mt-3 space-y-2">
                {evidenceSnippets(item).map((snippet) => (
                  <blockquote
                    key={snippet}
                    className="border-l-2 border-signal bg-slate-50 py-2 pl-3 text-sm leading-6 text-slate-700"
                  >
                    {snippet}
                  </blockquote>
                ))}
              </div>
            </article>
          ))}
        </div>
      </Card>
    </div>
  );
}

function MiniScore({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs font-semibold text-slate-500">
        <span>{label}</span>
        <span>{percent(value)}</span>
      </div>
      <ScoreBar value={value} />
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-ink">{value}</p>
    </div>
  );
}
