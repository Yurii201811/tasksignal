"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { AlertTriangle, ArrowRight, Play, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, ScoreBar } from "@/components/ui";

const colors = ["#0f766e", "#d97706", "#2563eb", "#7c3aed", "#dc2626"];
const scanDefaults: Record<string, string> = {
  hackernews: "ask",
  github: "manually copy paste is:issue is:open",
  stackexchange: "automation",
  reddit: "manual workflow automation",
};
const scanSourceOrder = ["hackernews", "github", "stackexchange", "reddit"];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request failed.";
}

export function Dashboard() {
  const queryClient = useQueryClient();
  const [scanSource, setScanSource] = useState("github");
  const [scanQuery, setScanQuery] = useState(scanDefaults.github);
  const [scanLimit, setScanLimit] = useState(30);
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const opportunities = useQuery({
    queryKey: ["opportunities"],
    queryFn: api.opportunities,
  });
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources });
  const scans = useQuery({ queryKey: ["scans"], queryFn: api.scans });
  const process = useMutation({
    mutationFn: api.processDemo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
    },
  });
  const runScan = useMutation({
    mutationFn: api.createScan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
    },
  });

  const metricCards = [
    ["Collected items", stats.data?.total_items ?? 0],
    ["Problem signals", stats.data?.problem_signals ?? 0],
    ["Clusters", stats.data?.clusters ?? 0],
    ["Opportunities", stats.data?.opportunities ?? 0],
  ];
  const topOpportunity = opportunities.data?.[0];
  const hasOpportunities = Boolean(opportunities.data?.length);
  const isLoadingWorkflow = stats.isLoading || opportunities.isLoading;
  const dataError =
    stats.error ?? opportunities.error ?? sources.error ?? scans.error ?? null;
  const processError = process.error ?? runScan.error ?? null;
  const sourceBreakdown = stats.data?.source_breakdown ?? [];
  const painDistribution = stats.data?.pain_distribution ?? [];
  const liveSources = (sources.data ?? [])
    .filter((source) => scanSourceOrder.includes(source.type))
    .sort(
      (left, right) =>
        scanSourceOrder.indexOf(left.type) - scanSourceOrder.indexOf(right.type),
    );
  const sourceOptions =
    liveSources.length > 0
      ? liveSources
      : scanSourceOrder.map((type) => ({
          id: type,
          name:
            type === "hackernews"
              ? "Hacker News"
              : type === "github"
                ? "GitHub Issues"
                : type === "stackexchange"
                  ? "Stack Exchange"
                  : "Reddit",
          type,
          config_json: {},
          enabled: true,
          created_at: "",
        }));
  const latestScan = scans.data?.[0];

  function updateScanSource(source: string) {
    setScanSource(source);
    setScanQuery(scanDefaults[source] ?? "");
  }

  function submitScan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    runScan.mutate({
      source: scanSource,
      query: scanQuery.trim(),
      limit: scanLimit,
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-3xl font-semibold text-ink">
            Opportunity dashboard
          </h1>
          <p className="mt-2 text-slate-600">
            Process fixture discussions into ranked, evidence-backed project
            ideas.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => process.mutate()}
            disabled={process.isPending}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-signal px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-wait disabled:opacity-70"
          >
            {process.isPending ? (
              <RefreshCw className="animate-spin" size={16} />
            ) : (
              <Play size={16} />
            )}
            {process.isPending ? "Processing fixtures" : "Process demo data"}
          </button>
        </div>
      </div>

      <Card>
        <form
          className="grid gap-4 lg:grid-cols-[minmax(180px,0.8fr)_minmax(260px,1.5fr)_120px_auto] lg:items-end"
          onSubmit={submitScan}
        >
          <label className="block">
            <span className="text-sm font-semibold text-slate-600">
              Live source
            </span>
            <select
              value={scanSource}
              onChange={(event) => updateScanSource(event.target.value)}
              className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-ink shadow-sm focus:border-signal focus:outline-none focus:ring-2 focus:ring-teal-100"
            >
              {sourceOptions.map((source) => (
                <option key={source.type} value={source.type}>
                  {source.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-slate-600">Query</span>
            <input
              value={scanQuery}
              onChange={(event) => setScanQuery(event.target.value)}
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-ink shadow-sm focus:border-signal focus:outline-none focus:ring-2 focus:ring-teal-100"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-slate-600">Limit</span>
            <input
              min={1}
              max={100}
              type="number"
              value={scanLimit}
              onChange={(event) =>
                setScanLimit(
                  Math.max(1, Math.min(100, Number(event.target.value) || 1)),
                )
              }
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-ink shadow-sm focus:border-signal focus:outline-none focus:ring-2 focus:ring-teal-100"
            />
          </label>
          <button
            type="submit"
            disabled={runScan.isPending}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-slate-50 disabled:cursor-wait disabled:opacity-70"
          >
            {runScan.isPending ? (
              <RefreshCw className="animate-spin" size={16} />
            ) : (
              <Play size={16} />
            )}
            {runScan.isPending ? "Running scan" : "Run scan"}
          </button>
        </form>
      </Card>

      {dataError && (
        <Card className="border-red-200 bg-red-50">
          <div className="flex gap-3 text-sm text-red-900">
            <AlertTriangle className="mt-0.5 shrink-0" size={16} />
            <div>
              <p className="font-semibold">Could not load the demo workflow.</p>
              <p className="mt-1 break-words text-red-800">
                {errorMessage(dataError)}
              </p>
            </div>
          </div>
        </Card>
      )}
      {processError && (
        <Card className="border-red-200 bg-red-50">
          <div className="flex gap-3 text-sm text-red-900">
            <AlertTriangle className="mt-0.5 shrink-0" size={16} />
            <div>
              <p className="font-semibold">Processing did not complete.</p>
              <p className="mt-1 break-words text-red-800">
                {errorMessage(processError)}
              </p>
            </div>
          </div>
        </Card>
      )}
      {process.data && (
        <Card className="border-teal-200 bg-teal-50">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm font-semibold text-teal-900">
              Demo processed: {process.data.raw_items_loaded} raw items,{" "}
              {process.data.signals_detected} signals,{" "}
              {process.data.clusters_created} clusters,{" "}
              {process.data.opportunities_created} opportunities.
            </p>
            {topOpportunity && (
              <Link
                href={`/opportunities/${topOpportunity.id}`}
                className="inline-flex items-center gap-1 text-sm font-semibold text-teal-900"
              >
                Open top opportunity <ArrowRight size={15} />
              </Link>
            )}
          </div>
        </Card>
      )}
      {latestScan && (
        <Card
          className={
            latestScan.status === "failed" ? "border-red-200 bg-red-50" : ""
          }
        >
          <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
            <div className="text-sm text-slate-600">
              <span className="font-semibold text-ink">Recent scan:</span>{" "}
              {latestScan.source_name ?? latestScan.source_type ?? "Selected source"}{" "}
              <Badge
                tone={
                  latestScan.status === "completed"
                    ? "green"
                    : latestScan.status === "failed"
                      ? "red"
                      : "blue"
                }
              >
                {latestScan.status}
              </Badge>
              <span className="ml-2">
                {latestScan.items_saved} saved from {latestScan.items_found} found
              </span>
              {latestScan.query ? (
                <span className="ml-2 text-slate-500">
                  Query: {latestScan.query}
                </span>
              ) : null}
            </div>
            {latestScan.status === "failed" && latestScan.error_message ? (
              <p className="text-sm font-medium text-red-800">
                {latestScan.error_message}
              </p>
            ) : null}
          </div>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metricCards.map(([label, value]) => (
          <Card key={label.toString()}>
            <p className="text-sm font-medium text-slate-500">{label}</p>
            <p className="mt-2 text-3xl font-semibold text-ink">{value}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
        <Card className="min-w-0">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-ink">
              Top opportunities
            </h2>
            <Badge tone="blue">Ranked by score</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-3 pr-4">Title</th>
                  <th className="py-3 pr-4">Score</th>
                  <th className="py-3 pr-4">Signals</th>
                  <th className="py-3 pr-4">Top source</th>
                  <th className="py-3 pr-4">Feasibility</th>
                  <th className="py-3 pr-4">Created</th>
                  <th className="py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {isLoadingWorkflow && (
                  <tr>
                    <td
                      colSpan={7}
                      className="py-8 text-center text-sm text-slate-500"
                    >
                      Loading fixture metrics and ranked opportunities...
                    </td>
                  </tr>
                )}
                {!isLoadingWorkflow && !hasOpportunities && (
                  <tr>
                    <td
                      colSpan={7}
                      className="py-8 text-center text-sm text-slate-500"
                    >
                      No ranked opportunities yet. Process demo data to generate
                      evidence-backed cards from fixtures.
                    </td>
                  </tr>
                )}
                {!isLoadingWorkflow &&
                  (opportunities.data ?? []).map((opportunity) => (
                    <tr
                      key={opportunity.id}
                      className="border-b border-slate-100"
                    >
                      <td className="max-w-md py-3 pr-4 font-medium text-ink">
                        {opportunity.title}
                      </td>
                      <td className="py-3 pr-4">
                        {Math.round(opportunity.opportunity_score * 100)}
                      </td>
                      <td className="py-3 pr-4">{opportunity.signal_count}</td>
                      <td className="py-3 pr-4">
                        <Badge>{opportunity.top_source}</Badge>
                      </td>
                      <td className="py-3 pr-4">
                        <div className="w-28">
                          <ScoreBar value={opportunity.feasibility_score} />
                        </div>
                      </td>
                      <td className="py-3 pr-4">
                        {new Date(opportunity.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3">
                        <Link
                          className="font-semibold text-signal"
                          href={`/opportunities/${opportunity.id}`}
                        >
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Card>
        <div className="grid min-w-0 gap-4 md:grid-cols-2 2xl:grid-cols-1">
          <Card>
            <h2 className="mb-4 text-lg font-semibold text-ink">
              Source breakdown
            </h2>
            <div className="h-56">
              {sourceBreakdown.length > 0 ? (
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={sourceBreakdown}
                      dataKey="count"
                      nameKey="source"
                      outerRadius={82}
                      label
                    >
                      {sourceBreakdown.map((entry, index) => (
                        <Cell
                          key={entry.source}
                          fill={colors[index % colors.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-center text-sm text-slate-500">
                  Source mix appears after fixture data is processed.
                </div>
              )}
            </div>
          </Card>
          <Card>
            <h2 className="mb-4 text-lg font-semibold text-ink">
              Pain score distribution
            </h2>
            <div className="h-56">
              {painDistribution.some((bucket) => bucket.count > 0) ? (
                <ResponsiveContainer>
                  <BarChart data={painDistribution}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#0f766e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-center text-sm text-slate-500">
                  Pain distribution appears after signals are detected.
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
