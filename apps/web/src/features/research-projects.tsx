"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarClock, Play, Plus, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  Input,
  PageHeader,
  Select,
  StateMessage,
} from "@/components/ui";
import type { ResearchProject } from "@/lib/types";
import {
  queryExamplesLabel,
  sourceQueryPresetByType,
  sourceQueryPresets,
} from "@/lib/source-query-presets";

const sourceOptions = sourceQueryPresets.map(({ value, label, defaultQuery }) => ({
  value,
  label,
  defaultQuery,
}));

const cadenceOptions = [
  { value: "manual", label: "Manual" },
  { value: "hourly", label: "Hourly" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "custom", label: "Custom" },
];

function errorMessage(error: unknown) {
  if (error instanceof Error) {
    try {
      const parsed = JSON.parse(error.message);
      if (parsed?.detail) {
        return typeof parsed.detail === "string"
          ? parsed.detail
          : JSON.stringify(parsed.detail);
      }
    } catch {
      return error.message;
    }
  }
  return "The request failed.";
}

function statusTone(status: string | null): "green" | "blue" | "red" | "slate" {
  if (status === "completed") return "green";
  if (status === "failed") return "red";
  if (status === "queued" || status === "running") return "blue";
  return "slate";
}

function formatDateTime(value: string | null) {
  if (!value) return "Not scheduled";
  return new Date(value).toLocaleString();
}

function sourceCapability(sourceType: string) {
  if (sourceType === "hackernews" || sourceType === "fixture") {
    return {
      tone: "green" as const,
      label: "Public/no secret",
      detail: "Runs from the browser without an operator token.",
    };
  }
  return {
    tone: "amber" as const,
    label: "Operator gated",
    detail:
      "Requires OPERATOR_SCAN_TOKEN on the API and the matching local token before browser runs.",
  };
}

function nextAction(project: ResearchProject) {
  if (!project.last_run_at) {
    return "Run this project to create scan history and ranked evidence.";
  }
  if (project.last_scan_status === "failed") {
    return "Open the scan detail to review the redacted connector error.";
  }
  if (project.next_run_at) {
    return `Next scheduled run: ${formatDateTime(project.next_run_at)}.`;
  }
  return "Manual project; run again when you want fresh evidence.";
}

export function ResearchProjects() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("Track CI/CD pain");
  const [description, setDescription] = useState(
    "Find repeated complaints that could become a focused developer-tool MVP.",
  );
  const [sourceType, setSourceType] = useState("hackernews");
  const [query, setQuery] = useState("ask");
  const [limit, setLimit] = useState(30);
  const [cadence, setCadence] = useState("manual");
  const [intervalHours, setIntervalHours] = useState(24);
  const [labels, setLabels] = useState("ci, developer-tools");
  const [operatorToken, setOperatorToken] = useState("");
  const [defaultsApplied, setDefaultsApplied] = useState(false);
  const localWorkspace = useQuery({
    queryKey: ["local-workspace"],
    queryFn: api.localWorkspace,
  });
  const projects = useQuery({
    queryKey: ["research-projects"],
    queryFn: api.researchProjects,
  });
  const scans = useQuery({ queryKey: ["scans"], queryFn: api.scans });
  const create = useMutation({
    mutationFn: api.createResearchProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-projects"] });
    },
  });
  const run = useMutation({
    mutationFn: (project: ResearchProject) =>
      api.runResearchProject(project.id, operatorToken.trim() || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-projects"] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    },
  });
  const runDue = useMutation({
    mutationFn: () =>
      api.runDueResearchProjects(operatorToken.trim() || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-projects"] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    },
  });

  useEffect(() => {
    setOperatorToken(
      window.localStorage.getItem("tasksignal.operatorToken") ?? "",
    );
  }, []);

  useEffect(() => {
    if (defaultsApplied || !localWorkspace.data?.configured) return;
    setSourceType(localWorkspace.data.default_source_type);
    setQuery(localWorkspace.data.default_query);
    setLimit(localWorkspace.data.default_limit);
    setCadence(localWorkspace.data.default_cadence);
    setIntervalHours(localWorkspace.data.default_schedule_interval_hours ?? 24);
    if (localWorkspace.data.workspace_goal) {
      setDescription(localWorkspace.data.workspace_goal);
    }
    setDefaultsApplied(true);
  }, [defaultsApplied, localWorkspace.data]);

  function updateOperatorToken(value: string) {
    setOperatorToken(value);
    window.localStorage.setItem("tasksignal.operatorToken", value);
  }

  function updateSource(value: string) {
    setSourceType(value);
    setQuery(
      sourceOptions.find((source) => source.value === value)?.defaultQuery ??
        "",
    );
  }

  function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate({
      name: name.trim(),
      description: description.trim() || null,
      source_type: sourceType,
      query: query.trim(),
      limit,
      cadence,
      schedule_interval_hours:
        cadence === "custom" ? Math.max(1, intervalHours) : null,
      labels: labels
        .split(",")
        .map((label) => label.trim())
        .filter(Boolean),
      enabled: true,
    });
  }

  const latestScan = scans.data?.[0];
  const selectedSourcePreset = sourceQueryPresetByType[sourceType];
  const selectedExamples = queryExamplesLabel(sourceType);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Research projects"
        description="Save source and query workflows, rerun them, and turn the strongest evidence into Codex task packs."
      />

      <Card variant="muted">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <h2 className="text-lg font-semibold text-ink">
              Repeatable research, not one-off scraping
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
              A project stores the source, query, limit, cadence, and labels so
              you can rerun the same evidence search, inspect its scan record,
              and export only opportunities with visible source context.
            </p>
          </div>
          <Link
            href="/settings"
            className="inline-flex min-h-11 items-center justify-center gap-2 whitespace-nowrap rounded-product border border-border-strong bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)] motion-safe:active:translate-y-px"
          >
            Workspace defaults <ArrowRight size={16} />
          </Link>
        </div>
      </Card>

      <Card>
        <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(260px,0.8fr)]">
          <form className="min-w-0 space-y-4" onSubmit={submitProject}>
            <div className="grid min-w-0 gap-4 sm:grid-cols-2">
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">
                  Project name
                </span>
                <Input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="mt-2"
                  required
                />
              </label>
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">Source</span>
                <Select
                  value={sourceType}
                  onChange={(event) => updateSource(event.target.value)}
                  className="mt-2"
                >
                  {sourceOptions.map((source) => (
                    <option key={source.value} value={source.value}>
                      {source.label}
                    </option>
                  ))}
                </Select>
              </label>
            </div>
            <label className="block min-w-0">
              <span className="text-sm font-semibold text-muted">
                Description
              </span>
              <Input
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="mt-2"
              />
            </label>
            <div className="grid min-w-0 gap-4 sm:grid-cols-[minmax(0,1fr)_120px]">
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">Query</span>
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="mt-2"
                />
                {selectedExamples ? (
                  <span className="mt-1 block text-xs leading-5 text-muted">
                    Examples: {selectedExamples}
                  </span>
                ) : null}
              </label>
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">Limit</span>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={limit}
                  onChange={(event) =>
                    setLimit(
                      Math.max(
                        1,
                        Math.min(100, Number(event.target.value) || 1),
                      ),
                    )
                  }
                  className="mt-2"
                />
              </label>
            </div>
            <label className="block min-w-0">
              <span className="text-sm font-semibold text-muted">Labels</span>
              <Input
                value={labels}
                onChange={(event) => setLabels(event.target.value)}
                className="mt-2"
              />
            </label>
            <div className="grid min-w-0 gap-4 sm:grid-cols-[minmax(0,1fr)_150px]">
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">
                  Cadence
                </span>
                <Select
                  value={cadence}
                  onChange={(event) => setCadence(event.target.value)}
                  className="mt-2"
                >
                  {cadenceOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">Hours</span>
                <Input
                  type="number"
                  min={1}
                  max={744}
                  value={intervalHours}
                  onChange={(event) =>
                    setIntervalHours(
                      Math.max(
                        1,
                        Math.min(744, Number(event.target.value) || 1),
                      ),
                    )
                  }
                  className="mt-2"
                  disabled={cadence !== "custom"}
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="submit"
                loading={create.isPending}
                disabled={create.isPending}
              >
                {create.isPending ? (
                  <RefreshCw className="motion-safe:animate-spin" size={16} />
                ) : (
                  <Plus size={16} />
                )}
                {create.isPending ? "Saving project" : "Save project"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => runDue.mutate()}
                loading={runDue.isPending}
                disabled={runDue.isPending}
              >
                {runDue.isPending ? (
                  <RefreshCw className="motion-safe:animate-spin" size={16} />
                ) : (
                  <CalendarClock size={16} />
                )}
                {runDue.isPending ? "Running due" : "Run due"}
              </Button>
            </div>
          </form>

          <div className="min-w-0 border-t border-border pt-4 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
            <p className="text-sm font-semibold text-ink">Operator token</p>
            <p className="mt-2 text-sm leading-6 text-muted">
              Public sources run without this. Credentialed GitHub, Reddit, and
              Stack Exchange browser runs require `OPERATOR_SCAN_TOKEN` on the
              API and the matching local token here.
            </p>
            {selectedSourcePreset ? (
              <div className="mt-3 border-t border-border pt-3 text-sm leading-6">
                <p className="font-semibold text-muted">Selected source</p>
                <p className="mt-1 text-ink">{selectedSourcePreset.credential}</p>
                <p className="mt-1 text-muted">{selectedSourcePreset.guidance}</p>
              </div>
            ) : null}
            <Input
              value={operatorToken}
              onChange={(event) => updateOperatorToken(event.target.value)}
              type="password"
              className="mt-3"
              placeholder="Local operator token"
            />
            {latestScan ? (
              <div className="mt-4 border-t border-border pt-4 text-sm">
                <p className="font-semibold text-muted">Latest scan</p>
                <p className="mt-1 text-ink">
                  {latestScan.source_name ?? latestScan.source_type}:{" "}
                  {latestScan.status}
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </Card>

      {create.error ? (
        <StateMessage tone="danger" title="Project was not saved">
          {errorMessage(create.error)}
        </StateMessage>
      ) : null}
      {create.data ? (
        <StateMessage tone="success" title="Research project saved">
          {create.data.name} is ready to run.
        </StateMessage>
      ) : null}
      {run.error ? (
        <StateMessage tone="danger" title="Project run did not complete">
          {errorMessage(run.error)}
        </StateMessage>
      ) : null}
      {run.data ? (
        <StateMessage tone="success" title="Project run finished">
          {run.data.items_saved} saved from {run.data.items_found} found.
          Signals: {run.data.signals_detected}. Opportunities:{" "}
          {run.data.opportunities_created}.
          {run.data.outcome_message ? ` ${run.data.outcome_message}` : ""}
        </StateMessage>
      ) : null}
      {runDue.error ? (
        <StateMessage tone="danger" title="Due projects did not complete">
          {errorMessage(runDue.error)}
        </StateMessage>
      ) : null}
      {runDue.data ? (
        <StateMessage tone="success" title="Due projects processed">
          {runDue.data.ran} ran and {runDue.data.skipped} skipped.
        </StateMessage>
      ) : null}

      {projects.error ? (
        <StateMessage tone="danger" title="Could not load projects">
          {errorMessage(projects.error)}
        </StateMessage>
      ) : null}
      {projects.isLoading ? (
        <StateMessage tone="info" title="Loading projects">
          Checking saved research workflows.
        </StateMessage>
      ) : null}

      <div className="grid gap-4">
        {(projects.data ?? []).length === 0 && !projects.isLoading ? (
          <StateMessage
            tone="warning"
            title="No saved research projects yet"
            action={
              <Link
                href="/settings"
                className="inline-flex min-h-11 items-center gap-1 whitespace-nowrap rounded-product px-2 text-sm font-semibold text-warning hover:bg-surface-warning focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-warning motion-safe:active:translate-y-px"
              >
                Set defaults <ArrowRight size={15} />
              </Link>
            }
          >
            Save a source and query above, then run it whenever you want fresh
            evidence.
          </StateMessage>
        ) : null}
        {(projects.data ?? []).map((project) => {
          const capability = sourceCapability(project.source_type);
          return (
          <Card key={project.id}>
            <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="blue">{project.source_type}</Badge>
                  <Badge tone={capability.tone}>{capability.label}</Badge>
                  <Badge tone={statusTone(project.last_scan_status)}>
                    {project.last_scan_status ?? "not run"}
                  </Badge>
                  {project.labels.map((label) => (
                    <Badge key={label}>{label}</Badge>
                  ))}
                </div>
                <h2 className="mt-3 break-words text-lg font-semibold text-ink">
                  {project.name}
                </h2>
                {project.description ? (
                  <p className="mt-1 break-words text-sm leading-6 text-muted">
                    {project.description}
                  </p>
                ) : null}
                <p className="mt-3 break-words text-sm text-muted">
                  Query:{" "}
                  <span className="font-mono text-ink">
                    {project.query || "-"}
                  </span>
                  {" · "}Limit: {project.limit}
                </p>
                <p className="mt-2 text-sm leading-6 text-muted">
                  {capability.detail}
                </p>
                <div className="mt-3 grid gap-2 text-sm text-muted sm:grid-cols-3">
                  <p>
                    Cadence:{" "}
                    <span className="font-medium text-ink">
                      {project.schedule_interval_hours
                        ? `${project.schedule_interval_hours}h`
                        : project.cadence}
                    </span>
                  </p>
                  <p>
                    Last:{" "}
                    <span className="font-medium text-ink">
                      {project.last_run_at
                        ? formatDateTime(project.last_run_at)
                        : "Never"}
                    </span>
                  </p>
                  <p>
                    Next:{" "}
                    <span className="font-medium text-ink">
                      {formatDateTime(project.next_run_at)}
                    </span>
                  </p>
                </div>
                <p className="mt-2 text-sm text-muted">
                  Runs:{" "}
                  <span className="font-medium text-ink">
                    {project.run_count}
                  </span>
                </p>
                <p className="mt-2 text-sm font-medium text-ink">
                  {nextAction(project)}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button
                  onClick={() => run.mutate(project)}
                  loading={run.isPending}
                  disabled={run.isPending}
                  variant="secondary"
                >
                  {run.isPending ? (
                    <RefreshCw className="motion-safe:animate-spin" size={16} />
                  ) : (
                    <Play size={16} />
                  )}
                  {run.isPending ? "Running" : "Run"}
                </Button>
                {project.last_scan_id ? (
                  <Link
                    href={`/scans/${project.last_scan_id}`}
                    className="inline-flex min-h-11 items-center justify-center gap-2 whitespace-nowrap rounded-product bg-signal px-4 py-2 text-sm font-semibold text-[var(--color-accent-ink)] hover:bg-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)] motion-safe:active:translate-y-px"
                  >
                    Scan detail <ArrowRight size={16} />
                  </Link>
                ) : null}
              </div>
            </div>
          </Card>
        );
        })}
      </div>
    </div>
  );
}
