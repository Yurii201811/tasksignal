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
import {
  ArrowRight,
  CheckCircle2,
  FileText,
  FolderKanban,
  Play,
  RefreshCw,
  Settings,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  Input,
  MetricTile,
  PageHeader,
  ScoreBar,
  Select,
  StateMessage,
  TableShell,
} from "@/components/ui";

const chartColors = [
  "var(--ts-chart-1)",
  "var(--ts-chart-2)",
  "var(--ts-chart-3)",
  "var(--ts-chart-4)",
  "var(--ts-chart-5)",
];
const scanDefaults: Record<string, string> = {
  hackernews: "ask",
};
const scanGuidance: Record<
  string,
  { credential: string; query: string; privacy: string }
> = {
  hackernews: {
    credential: "No credentials required.",
    query:
      "Use ask, new, top, best, show, or job; other text filters Ask HN client-side.",
    privacy: "Stores source URLs and normalized public post fields.",
  },
};
const scanSourceOrder = ["hackernews"];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request failed.";
}

export function Dashboard() {
  const queryClient = useQueryClient();
  const [scanSource, setScanSource] = useState("hackernews");
  const [scanQuery, setScanQuery] = useState(scanDefaults.hackernews);
  const [scanLimit, setScanLimit] = useState(30);
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const opportunities = useQuery({
    queryKey: ["opportunities"],
    queryFn: api.opportunities,
  });
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources });
  const scans = useQuery({ queryKey: ["scans"], queryFn: api.scans });
  const readiness = useQuery({
    queryKey: ["readiness"],
    queryFn: api.readiness,
  });
  const process = useMutation({
    mutationFn: api.processDemo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["readiness"] });
    },
  });
  const runScan = useMutation({
    mutationFn: api.createScan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["readiness"] });
    },
  });

  const metricCards = [
    {
      label: "Collected items",
      value: stats.data?.total_items ?? 0,
      hint: "Raw public-source items available locally",
    },
    {
      label: "Problem signals",
      value: stats.data?.problem_signals ?? 0,
      hint: "Detected pain, task, or buying-intent signals",
    },
    {
      label: "Clusters",
      value: stats.data?.clusters ?? 0,
      hint: "Grouped signals that may describe the same problem",
    },
    {
      label: "Opportunities",
      value: stats.data?.opportunities ?? 0,
      hint: "Ranked ideas generated from evidence",
    },
  ];
  const topOpportunity = opportunities.data?.[0];
  const hasOpportunities = Boolean(opportunities.data?.length);
  const isLoadingWorkflow = stats.isLoading || opportunities.isLoading;
  const dataError =
    stats.error ?? opportunities.error ?? sources.error ?? scans.error ?? null;
  const processError = process.error ?? null;
  const scanError = runScan.error ?? null;
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
              : type,
          type,
          config_json: {},
          enabled: true,
          created_at: "",
        }));
  const latestScan = scans.data?.[0];
  const latestScanTone: "info" | "success" | "danger" =
    latestScan?.status === "failed"
      ? "danger"
      : latestScan?.status === "completed"
        ? "success"
        : "info";
  const selectedScanGuidance = scanGuidance[scanSource];
  const readinessChecks = readiness.data?.checks;
  const publicScanSources = readinessChecks?.public_scan_sources as
    | string[]
    | undefined;
  const publicScanSourcesLabel = readiness.data
    ? publicScanSources?.length
      ? publicScanSources.join(", ")
      : "none enabled"
    : "checking";
  const workflowSteps = [
    {
      label: "Set workspace defaults",
      description: "Store the local owner, research focus, source, query, and cadence for this machine.",
      href: "/settings",
      icon: Settings,
      done: Boolean(readinessChecks?.local_workspace_configured),
      action: "Open integrations",
    },
    {
      label: "Save a research project",
      description: "Keep a source/query workflow that can be rerun manually or on a cadence.",
      href: "/projects",
      icon: FolderKanban,
      done: Number(readinessChecks?.projects ?? 0) > 0,
      action: "Create project",
    },
    {
      label: "Generate ranked opportunities",
      description: "Run fixtures or a public scan, then inspect the evidence trail behind each score.",
      href: "#top-opportunities",
      icon: CheckCircle2,
      done: Number(readinessChecks?.opportunities ?? 0) > 0,
      action: "Review results",
    },
    {
      label: "Export a task pack",
      description: "Open an opportunity and export evidence, acceptance criteria, and privacy constraints for Codex.",
      href: topOpportunity ? `/opportunities/${topOpportunity.id}` : "/dashboard",
      icon: FileText,
      done: Boolean(readinessChecks?.codex_task_packs && topOpportunity),
      action: topOpportunity ? "Open top opportunity" : "Run first",
    },
  ];

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
      <PageHeader
        title="Opportunity dashboard"
        description="Process public-source discussions into ranked, evidence-backed project ideas, then inspect the signals behind each score."
        actions={
          <Button
            onClick={() => process.mutate()}
            loading={process.isPending}
            disabled={process.isPending}
          >
            {process.isPending ? (
              <RefreshCw className="animate-spin" size={16} />
            ) : (
              <Play size={16} />
            )}
            {process.isPending ? "Processing fixtures" : "Process demo data"}
          </Button>
        }
      />

      <Card variant="muted">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <div className="flex flex-wrap gap-2">
              <Badge tone={readiness.data?.status === "ready" ? "green" : "amber"}>
                {readiness.data?.status ?? "checking"}
              </Badge>
              <Badge>
                Public sources: {publicScanSourcesLabel}
              </Badge>
            </div>
            <h2 className="mt-3 text-lg font-semibold text-ink">
              First useful run
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
              TaskSignal is most useful when a saved workflow, scan history,
              ranked evidence, and export path all exist together. These steps
              use the current local database state.
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={() => readiness.refetch()}
            loading={readiness.isFetching}
            disabled={readiness.isFetching}
          >
            <RefreshCw
              size={16}
              className={readiness.isFetching ? "animate-spin" : ""}
            />
            Refresh readiness
          </Button>
        </div>

        {readiness.error ? (
          <StateMessage tone="danger" title="Readiness check failed" className="mt-4">
            {errorMessage(readiness.error)}
          </StateMessage>
        ) : null}

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {workflowSteps.map((step) => (
            <Link
              key={step.label}
              href={step.href}
              className="group rounded-product border border-border bg-surface p-4 shadow-soft motion-safe:transition-[border-color,background-color] motion-safe:duration-200 hover:border-border-strong hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="rounded-product bg-surface-muted p-2 text-signal group-hover:bg-surface">
                  <step.icon size={18} />
                </span>
                <Badge tone={step.done ? "green" : "amber"}>
                  {step.done ? "Done" : "Next"}
                </Badge>
              </div>
              <p className="mt-3 text-sm font-semibold text-ink">{step.label}</p>
              <p className="mt-1 text-sm leading-6 text-muted">
                {step.description}
              </p>
              <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-signal">
                {step.action} <ArrowRight size={14} />
              </span>
            </Link>
          ))}
        </div>

        {readiness.data?.warnings.length ? (
          <div className="mt-4 border-t border-border pt-4">
            <p className="text-sm font-semibold text-muted">Current warnings</p>
            <ul className="mt-2 grid gap-1 text-sm leading-6 text-muted">
              {readiness.data.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>

      <Card>
        <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
          <div>
            <div className="flex flex-wrap gap-2">
              <Badge tone="green">Fixture mode works without credentials</Badge>
              <Badge tone="blue">Live scan is optional</Badge>
            </div>
            <h2 className="mt-3 text-lg font-semibold text-ink">
              Run the discovery loop
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
              Start with demo data for a reliable review path, or run a
              public Hacker News scan. Credentialed sources are reserved for
              trusted internal jobs so public callers cannot spend server-side
              tokens. The ranking pass remains local-first and does not require
              a paid LLM.
            </p>
          </div>
          {latestScan ? (
            <Badge
              tone={
                latestScan.status === "completed"
                  ? "green"
                  : latestScan.status === "failed"
                    ? "red"
                    : "blue"
              }
            >
              Latest scan: {latestScan.status}
            </Badge>
          ) : null}
        </div>
        <form
          className="grid gap-4 lg:grid-cols-[minmax(180px,0.8fr)_minmax(260px,1.5fr)_120px_auto] lg:items-end"
          onSubmit={submitScan}
        >
          <label className="block">
            <span className="text-sm font-semibold text-muted">Live source</span>
            <Select
              value={scanSource}
              onChange={(event) => updateScanSource(event.target.value)}
              className="mt-2"
            >
              {sourceOptions.map((source) => (
                <option key={source.type} value={source.type}>
                  {source.name}
                </option>
              ))}
            </Select>
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-muted">Query</span>
            <Input
              value={scanQuery}
              onChange={(event) => setScanQuery(event.target.value)}
              className="mt-2"
              placeholder="Search phrase or issue query"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-muted">Limit</span>
            <Input
              min={1}
              max={100}
              type="number"
              value={scanLimit}
              onChange={(event) =>
                setScanLimit(
                  Math.max(1, Math.min(100, Number(event.target.value) || 1)),
                )
              }
              className="mt-2"
            />
          </label>
          <Button
            type="submit"
            variant="secondary"
            loading={runScan.isPending}
            disabled={runScan.isPending}
          >
            {runScan.isPending ? (
              <RefreshCw className="animate-spin" size={16} />
            ) : (
              <Play size={16} />
            )}
            {runScan.isPending ? "Running scan" : "Run scan"}
          </Button>
        </form>

        <div className="mt-3 text-xs leading-5 text-muted">
          Default queries are intentionally modest so reviewers can see the
          workflow before widening a live scan through trusted internal jobs.
        </div>

        {selectedScanGuidance ? (
          <div className="mt-4 rounded-product border border-border bg-surface-muted p-4">
            <p className="text-sm font-semibold text-ink">Connector guidance</p>
            <dl className="mt-3 grid gap-3 text-sm leading-6 sm:grid-cols-3">
              <div>
                <dt className="font-semibold text-muted">Credential</dt>
                <dd className="mt-1 break-words text-ink">
                  {selectedScanGuidance.credential}
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-muted">Query</dt>
                <dd className="mt-1 break-words text-ink">
                  {selectedScanGuidance.query}
                </dd>
              </div>
              <div>
                <dt className="font-semibold text-muted">Privacy</dt>
                <dd className="mt-1 break-words text-ink">
                  {selectedScanGuidance.privacy}
                </dd>
              </div>
            </dl>
          </div>
        ) : null}

        {scanError ? (
          <StateMessage tone="danger" title="Live scan did not complete" className="mt-4">
            {errorMessage(scanError)}
          </StateMessage>
        ) : null}
        {runScan.data ? (
          <StateMessage tone="success" title="Live scan response received" className="mt-4">
            {runScan.data.items_saved} saved from {runScan.data.items_found} found.
            Signals: {runScan.data.signals_detected}. Opportunities:{" "}
            {runScan.data.opportunities_created}. Status: {runScan.data.status}.
            {runScan.data.outcome_message ? ` ${runScan.data.outcome_message}` : ""}
          </StateMessage>
        ) : null}
      </Card>

      {dataError && (
        <StateMessage tone="danger" title="Could not load dashboard data">
          {errorMessage(dataError)}
        </StateMessage>
      )}
      {processError && (
        <StateMessage tone="danger" title="Demo processing did not complete">
          {errorMessage(processError)}
        </StateMessage>
      )}
      {process.data && (
        <StateMessage
          tone="success"
          title={`Demo processed: ${process.data.raw_items_loaded} raw items, ${process.data.signals_detected} signals, ${process.data.clusters_created} clusters, ${process.data.opportunities_created} opportunities.`}
          action={
            topOpportunity ? (
              <Link
                href={`/opportunities/${topOpportunity.id}`}
                className="inline-flex min-h-9 items-center gap-1 rounded-product px-2 text-sm font-semibold text-success hover:bg-surface-success focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-success"
              >
                Open top opportunity <ArrowRight size={15} />
              </Link>
            ) : null
          }
        />
      )}
      {latestScan && (
        <StateMessage
          tone={latestScanTone}
          title={`Recent scan: ${latestScan.source_name ?? latestScan.source_type ?? "Selected source"} (${latestScan.status})`}
        >
          <span className="break-words">
            {latestScan.items_saved} saved from {latestScan.items_found} found.
            {` Signals: ${latestScan.signals_detected}. Opportunities: ${latestScan.opportunities_created}.`}
            {latestScan.query ? ` Query: ${latestScan.query}.` : ""}
            {latestScan.outcome_message ? ` Outcome: ${latestScan.outcome_message}` : ""}
            {latestScan.status === "failed" && latestScan.error_message
              ? ` Error: ${latestScan.error_message}`
              : ""}
          </span>
        </StateMessage>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metricCards.map((metric) => (
          <MetricTile
            key={metric.label}
            label={metric.label}
            value={metric.value}
            hint={metric.hint}
          />
        ))}
      </div>

      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
        <Card className="min-w-0" id="top-opportunities">
          <div className="mb-4 flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-lg font-semibold text-ink">
                Top opportunities
              </h2>
              <p className="mt-1 text-sm text-muted">
                Ranked from real evidence fields, with score and source context
                kept visible.
              </p>
            </div>
            <Badge tone="blue">Ranked by computed score</Badge>
          </div>

          <TableShell tableClassName="min-w-[760px]">
            <thead className="border-b border-border text-xs uppercase text-muted">
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
                <>
                  <tr>
                    <td colSpan={7} className="py-4">
                      <div className="h-3 w-3/4 animate-pulse rounded-full bg-surface-muted" />
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={7} className="py-4">
                      <div className="h-3 w-1/2 animate-pulse rounded-full bg-surface-muted" />
                    </td>
                  </tr>
                </>
              )}
              {!isLoadingWorkflow && !hasOpportunities && (
                <tr>
                  <td colSpan={7} className="py-8 text-center">
                    <div className="mx-auto max-w-md rounded-product border border-dashed border-border bg-surface-muted px-4 py-6">
                      <p className="text-sm font-semibold text-ink">
                        No ranked opportunities yet
                      </p>
                      <p className="mt-2 text-sm leading-6 text-muted">
                        Process demo data to generate evidence-backed cards from
                        fixtures, then open the top result for its source trail.
                      </p>
                    </div>
                  </td>
                </tr>
              )}
              {!isLoadingWorkflow &&
                (opportunities.data ?? []).map((opportunity) => (
                  <tr
                    key={opportunity.id}
                    className="border-b border-border last:border-b-0"
                  >
                    <td className="max-w-md py-3 pr-4">
                      <Link
                        href={`/opportunities/${opportunity.id}`}
                        className="font-semibold text-ink hover:text-signal"
                      >
                        {opportunity.title}
                      </Link>
                    </td>
                    <td className="py-3 pr-4">
                      <span className="font-semibold tabular-nums text-ink">
                        {Math.round(opportunity.opportunity_score * 100)}
                      </span>
                    </td>
                    <td className="py-3 pr-4 tabular-nums">
                      {opportunity.signal_count}
                    </td>
                    <td className="py-3 pr-4">
                      <Badge>{opportunity.top_source}</Badge>
                    </td>
                    <td className="py-3 pr-4">
                      <div className="w-28">
                        <ScoreBar value={opportunity.feasibility_score} />
                      </div>
                    </td>
                    <td className="py-3 pr-4 text-muted">
                      {new Date(opportunity.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3">
                      <Link
                        className="inline-flex items-center gap-1 font-semibold text-signal hover:text-[var(--ts-accent-hover)]"
                        href={`/opportunities/${opportunity.id}`}
                      >
                        Open <ArrowRight size={14} />
                      </Link>
                    </td>
                  </tr>
                ))}
            </tbody>
          </TableShell>
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
                          fill={chartColors[index % chartColors.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        borderColor: "var(--ts-border)",
                        borderRadius: 8,
                        color: "var(--ts-text)",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center rounded-product border border-dashed border-border bg-surface-muted px-4 text-center text-sm text-muted">
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
                    <Tooltip
                      contentStyle={{
                        borderColor: "var(--ts-border)",
                        borderRadius: 8,
                        color: "var(--ts-text)",
                      }}
                    />
                    <Bar
                      dataKey="count"
                      fill="var(--ts-chart-1)"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center rounded-product border border-dashed border-border bg-surface-muted px-4 text-center text-sm text-muted">
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
