"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, RotateCw } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, ScoreBar } from "@/components/ui";

export function OpportunityDetail({ id }: { id: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["opportunity", id], queryFn: () => api.opportunity(id) });
  const regenerate = useMutation({
    mutationFn: () => api.regenerateOpportunity(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["opportunity", id] })
  });

  if (isLoading) return <Card>Loading opportunity...</Card>;
  if (!data) return <Card>Opportunity not found. Process demo data from the dashboard first.</Card>;

  const breakdown = data.scoring_breakdown_json;
  const scoreRows = [
    ["Frequency", breakdown.frequency],
    ["Recency", breakdown.recency],
    ["Pain intensity", breakdown.pain_intensity],
    ["Task concreteness", breakdown.task_concreteness],
    ["Buying intent", breakdown.buying_intent],
    ["Feasibility", breakdown.feasibility],
    ["Competition penalty", breakdown.competition_penalty]
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
        <div>
          <Link href="/dashboard" className="text-sm font-semibold text-signal">Back to dashboard</Link>
          <h1 className="mt-3 max-w-4xl text-3xl font-semibold leading-tight text-ink">{data.title}</h1>
          <p className="mt-3 max-w-4xl text-slate-600">{data.problem_statement}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/opportunities/${id}/prompt`} className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white">
            <FileText size={16} /> View Codex Prompt
          </Link>
          <a href={api.exportUrl(id)} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink">
            <Download size={16} /> Export Markdown
          </a>
          <button
            onClick={() => regenerate.mutate()}
            disabled={regenerate.isPending}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink disabled:cursor-wait disabled:opacity-70"
          >
            <RotateCw size={16} className={regenerate.isPending ? "animate-spin" : ""} /> Regenerate
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
          {Array.isArray(data.scoring_breakdown_json.common_phrases) && (
            <div>
              <p className="text-sm font-semibold text-slate-500">Common phrases</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {data.scoring_breakdown_json.common_phrases.map((phrase) => (
                  <Badge key={String(phrase)}>{String(phrase)}</Badge>
                ))}
              </div>
            </div>
          )}
        </Card>
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-ink">Scoring breakdown</h2>
            <span className="text-3xl font-semibold text-signal">{Math.round(data.opportunity_score * 100)}</span>
          </div>
          <div className="mt-5 space-y-4">
            {scoreRows.map(([label, value]) => (
              <div key={label as string}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="font-medium text-slate-600">{label}</span>
                  <span>{typeof value === "number" ? Math.round(value * 100) : 0}</span>
                </div>
                <ScoreBar value={typeof value === "number" ? value : 0} />
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm text-slate-600">{String(breakdown.explanation ?? "")}</p>
        </Card>
      </div>

      <Card>
        <h2 className="text-lg font-semibold text-ink">Evidence items</h2>
        <div className="mt-4 grid gap-4">
          {data.evidence_items.map((item) => (
            <article key={item.id} className="rounded-lg border border-slate-200 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="blue">{item.source}</Badge>
                <Badge tone="green">{item.signal_type}</Badge>
                <span className="text-xs font-semibold text-slate-500">Pain {Math.round(item.pain_score * 100)}</span>
              </div>
              <h3 className="mt-3 font-semibold text-ink">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{item.body.slice(0, 240)}...</p>
              {item.url && <a href={item.url} className="mt-2 inline-block text-sm font-semibold text-signal">Source link</a>}
            </article>
          ))}
        </div>
      </Card>
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
