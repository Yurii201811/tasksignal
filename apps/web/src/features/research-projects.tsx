"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  CalendarClock,
  ChevronDown,
  GitCompareArrows,
  Play,
  Plus,
  RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
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

const sourceOptions = sourceQueryPresets.map(
  ({ value, label, defaultQuery }) => ({
    value,
    label,
    defaultQuery,
  }),
);

const cadenceOptions = [
  { value: "manual", label: "Manual" },
  { value: "hourly", label: "Hourly" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "custom", label: "Custom" },
];

type RunStatusFilter = "all" | "not_run" | "completed" | "failed";

// Only statuses the saved-project data actually carries get a filter. Rare
// transitional states (queued/running) and unknown strings stay under "All".
const runStatusOptions: {
  value: Exclude<RunStatusFilter, "all">;
  label: string;
}[] = [
  { value: "not_run", label: "Not run" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

const secondaryLinkClass =
  "inline-flex min-h-11 items-center justify-center gap-2 whitespace-nowrap rounded-product border border-border-strong bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)] motion-safe:active:translate-y-px";

const summaryClass =
  "flex cursor-pointer list-none items-center justify-between gap-3 rounded-product text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--ts-focus-ring)]";

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

function runStatusOf(
  project: ResearchProject,
): Exclude<RunStatusFilter, "all"> | "other" {
  const status = project.last_scan_status;
  if (!status) return "not_run";
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  return "other";
}

function matchesProjectSearch(project: ResearchProject, term: string) {
  if (!term) return true;
  const haystack = [
    project.name,
    project.description ?? "",
    project.query,
    project.source_type,
    sourceQueryPresetByType[project.source_type]?.label ?? "",
    ...project.labels,
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(term);
}

function revealCreateForm(
  section: HTMLElement | null,
  input: HTMLInputElement | null,
) {
  if (section && typeof section.scrollIntoView === "function") {
    section.scrollIntoView({ block: "start" });
  }
  input?.focus({ preventScroll: true });
}

export function ResearchProjects() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("Track CI/CD pain");
  const [description, setDescription] = useState(
    "Find repeated complaints that could become a focused developer-tool MVP.",
  );
  const [sourceType, setSourceType] = useState("hackernews");
  const [sourceId, setSourceId] = useState("");
  const [query, setQuery] = useState("ask");
  const [limit, setLimit] = useState(30);
  const [cadence, setCadence] = useState("manual");
  const [intervalHours, setIntervalHours] = useState(24);
  const [labels, setLabels] = useState("ci, developer-tools");
  const [operatorToken, setOperatorToken] = useState("");
  const [defaultsApplied, setDefaultsApplied] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [runStatusFilter, setRunStatusFilter] =
    useState<RunStatusFilter>("all");
  // null means "not decided yet": the form opens itself only for a truly
  // empty, successfully loaded list. Once opened it stays open until the
  // operator collapses it, so saving never hides the focused control.
  const [createOpen, setCreateOpen] = useState<boolean | null>(null);
  const pendingFocusRef = useRef(false);
  const createSectionRef = useRef<HTMLDetailsElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const localWorkspace = useQuery({
    queryKey: ["local-workspace"],
    queryFn: api.localWorkspace,
  });
  const projects = useQuery({
    queryKey: ["research-projects"],
    queryFn: api.researchProjects,
  });
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources });
  const scans = useQuery({ queryKey: ["scans"], queryFn: api.scans });
  const create = useMutation({
    mutationFn: api.createResearchProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-projects"] });
      queryClient.invalidateQueries({ queryKey: ["readiness"] });
    },
  });
  const run = useMutation({
    mutationFn: (project: ResearchProject) =>
      api.runResearchProject(project.id, operatorToken.trim() || undefined),
    onSuccess: (_scan, project) => {
      queryClient.invalidateQueries({ queryKey: ["research-projects"] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      queryClient.invalidateQueries({ queryKey: ["opportunity-threads"] });
      queryClient.invalidateQueries({ queryKey: ["readiness"] });
      queryClient.invalidateQueries({ queryKey: ["evaluation"] });
      queryClient.invalidateQueries({
        queryKey: ["research-project", project.id],
      });
      queryClient.invalidateQueries({
        queryKey: ["research-project-runs", project.id],
      });
      queryClient.invalidateQueries({
        queryKey: ["research-project-run-delta", project.id],
      });
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
      queryClient.invalidateQueries({ queryKey: ["opportunity-threads"] });
      queryClient.invalidateQueries({ queryKey: ["readiness"] });
      queryClient.invalidateQueries({ queryKey: ["evaluation"] });
      // Due runs can touch any project, so refresh every per-project cache.
      queryClient.invalidateQueries({ queryKey: ["research-project"] });
      queryClient.invalidateQueries({ queryKey: ["research-project-runs"] });
      queryClient.invalidateQueries({
        queryKey: ["research-project-run-delta"],
      });
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

  useEffect(() => {
    if (
      createOpen === null &&
      projects.isSuccess &&
      projects.data.length === 0
    ) {
      setCreateOpen(true);
    }
  }, [createOpen, projects.isSuccess, projects.data]);

  const createExpanded = createOpen ?? false;

  useEffect(() => {
    if (!pendingFocusRef.current || !createExpanded) return;
    pendingFocusRef.current = false;
    revealCreateForm(createSectionRef.current, nameInputRef.current);
  }, [createExpanded]);

  function openCreateForm() {
    if (createExpanded) {
      revealCreateForm(createSectionRef.current, nameInputRef.current);
      return;
    }
    pendingFocusRef.current = true;
    setCreateOpen(true);
  }

  function updateOperatorToken(value: string) {
    setOperatorToken(value);
    window.localStorage.setItem("tasksignal.operatorToken", value);
  }

  function updateSource(value: string) {
    setSourceType(value);
    setSourceId("");
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
      source_id: sourceType === "discourse" ? sourceId || null : null,
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

  function clearProjectFilters() {
    setProjectSearch("");
    setRunStatusFilter("all");
  }

  const latestScan = scans.data?.[0];
  const selectedSourcePreset = sourceQueryPresetByType[sourceType];
  const selectedExamples = queryExamplesLabel(sourceType);
  const discourseSources = (sources.data ?? []).filter(
    (source) => source.type === "discourse" && source.enabled,
  );
  // "empty" is only claimed after a successful load; pending and failed
  // source requests get their own states so the form never says "add a
  // forum" while the real answer is still unknown.
  const discourseSourcesState: "loading" | "error" | "empty" | "ready" =
    discourseSources.length > 0
      ? "ready"
      : sources.isPending
        ? "loading"
        : sources.isError
          ? "error"
          : "empty";

  const savedProjects = projects.data ?? [];
  const hasProjects = savedProjects.length > 0;
  const listIsEmpty = projects.isSuccess && savedProjects.length === 0;
  const normalizedSearch = projectSearch.trim().toLowerCase();
  const statusCounts = savedProjects.reduce<
    Record<Exclude<RunStatusFilter, "all">, number>
  >(
    (counts, project) => {
      const status = runStatusOf(project);
      if (status !== "other") counts[status] += 1;
      return counts;
    },
    { not_run: 0, completed: 0, failed: 0 },
  );
  const visibleProjects = savedProjects.filter(
    (project) =>
      matchesProjectSearch(project, normalizedSearch) &&
      (runStatusFilter === "all" || runStatusOf(project) === runStatusFilter),
  );
  const activeStatusLabel = runStatusOptions.find(
    (option) => option.value === runStatusFilter,
  )?.label;
  const resultSummary = `Showing ${visibleProjects.length} of ${savedProjects.length} saved projects${
    normalizedSearch ? ` matching “${projectSearch.trim()}”` : ""
  }${activeStatusLabel ? ` · ${activeStatusLabel}` : ""}`;
  const hasOperatorToken = operatorToken.trim().length > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Research projects"
        description="Save source and query workflows, rerun them, and turn the strongest evidence into Codex task packs."
        actions={
          <>
            <Link href="/settings" className={secondaryLinkClass}>
              Workspace defaults <ArrowRight size={16} aria-hidden />
            </Link>
            <Button onClick={openCreateForm}>
              <Plus size={16} aria-hidden /> New project
            </Button>
          </>
        }
      />

      <section aria-labelledby="saved-projects-heading" className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <h2
              id="saved-projects-heading"
              className="text-lg font-semibold text-ink"
            >
              Saved projects
            </h2>
            {projects.data ? <Badge>{savedProjects.length} saved</Badge> : null}
            {latestScan ? (
              <Badge tone={statusTone(latestScan.status)}>
                Latest scan: {latestScan.status}
              </Badge>
            ) : null}
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={() => runDue.mutate()}
            loading={runDue.isPending}
            disabled={runDue.isPending}
            className="sm:shrink-0"
          >
            {runDue.isPending ? (
              <RefreshCw
                className="motion-safe:animate-spin"
                size={16}
                aria-hidden
              />
            ) : (
              <CalendarClock size={16} aria-hidden />
            )}
            {runDue.isPending ? "Running due" : "Run due"}
          </Button>
        </div>

        {projects.error ? (
          <StateMessage
            tone="danger"
            title="Could not load projects"
            action={
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void projects.refetch()}
                loading={projects.isFetching}
                disabled={projects.isFetching}
              >
                <RefreshCw
                  size={15}
                  aria-hidden
                  className={
                    projects.isFetching ? "motion-safe:animate-spin" : undefined
                  }
                />
                {projects.isFetching ? "Retrying" : "Retry"}
              </Button>
            }
          >
            {errorMessage(projects.error)}{" "}
            {projects.data
              ? "The last loaded list stays below until a retry succeeds."
              : "Check that the local API is running, then retry."}
          </StateMessage>
        ) : null}
        {projects.isLoading ? (
          <StateMessage tone="info" title="Loading projects">
            Checking saved research workflows.
          </StateMessage>
        ) : null}

        {hasProjects ? (
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <label className="block min-w-0">
              <span className="text-sm font-semibold text-muted">
                Search projects
              </span>
              <Input
                type="search"
                value={projectSearch}
                onChange={(event) => setProjectSearch(event.target.value)}
                className="mt-2"
                placeholder="Name, query, label, or source"
              />
            </label>
            <div
              role="group"
              aria-label="Run status filter"
              className="flex flex-wrap gap-2"
            >
              <Button
                size="sm"
                variant={runStatusFilter === "all" ? "primary" : "secondary"}
                aria-pressed={runStatusFilter === "all"}
                onClick={() => setRunStatusFilter("all")}
              >
                All {savedProjects.length}
              </Button>
              {runStatusOptions.map((option) => (
                <Button
                  key={option.value}
                  size="sm"
                  variant={
                    runStatusFilter === option.value ? "primary" : "secondary"
                  }
                  aria-pressed={runStatusFilter === option.value}
                  onClick={() => setRunStatusFilter(option.value)}
                >
                  {option.label} {statusCounts[option.value]}
                </Button>
              ))}
            </div>
          </div>
        ) : null}
        {hasProjects ? (
          <p
            className="text-sm text-muted"
            aria-live="polite"
            aria-atomic="true"
          >
            {resultSummary}
          </p>
        ) : null}

        <details className="group rounded-product border border-border bg-surface-muted">
          <summary
            className={`${summaryClass} min-h-11 px-4 py-2 text-sm font-semibold hover:bg-surface`}
          >
            <span className="flex flex-wrap items-center gap-2">
              Operator token for gated runs
              <Badge tone={hasOperatorToken ? "green" : "slate"}>
                {hasOperatorToken ? "Saved locally" : "Not set"}
              </Badge>
            </span>
            <ChevronDown
              size={16}
              className="shrink-0 motion-safe:transition-transform motion-safe:group-open:rotate-180"
              aria-hidden
            />
          </summary>
          <div className="border-t border-border p-4">
            <p className="text-sm leading-6 text-muted">
              Public sources run without this. Credentialed GitHub, Reddit, and
              Stack Exchange browser runs require `OPERATOR_SCAN_TOKEN` on the
              API and the matching local token here.
            </p>
            <label className="mt-3 block max-w-md">
              <span className="text-sm font-semibold text-muted">
                Local operator token
              </span>
              <Input
                value={operatorToken}
                onChange={(event) => updateOperatorToken(event.target.value)}
                type="password"
                className="mt-2"
              />
            </label>
          </div>
        </details>

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

        {listIsEmpty ? (
          <StateMessage
            tone="warning"
            title="No saved research projects yet"
            action={
              <Link
                href="/settings"
                className="inline-flex min-h-11 items-center gap-1 whitespace-nowrap rounded-product px-2 text-sm font-semibold text-warning hover:bg-surface-warning focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-warning motion-safe:active:translate-y-px"
              >
                Set defaults <ArrowRight size={15} aria-hidden />
              </Link>
            }
          >
            Save a source and query in the New project form below, then run it
            whenever you want fresh evidence.
          </StateMessage>
        ) : null}
        {hasProjects && visibleProjects.length === 0 ? (
          <EmptyState
            title="No projects match these filters"
            description="Try a different search term or run status."
            action={
              <Button
                variant="secondary"
                size="sm"
                onClick={clearProjectFilters}
              >
                Clear filters
              </Button>
            }
          />
        ) : null}

        {visibleProjects.length > 0 ? (
          <ul role="list" className="grid gap-4">
            {visibleProjects.map((project) => {
              const capability = sourceCapability(project.source_type);
              const isRunningThis =
                run.isPending && run.variables?.id === project.id;
              return (
                <li key={project.id} className="min-w-0">
                  <Card>
                    <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone="blue">{project.source_type}</Badge>
                          <Badge tone={capability.tone}>
                            {capability.label}
                          </Badge>
                          <Badge tone={statusTone(project.last_scan_status)}>
                            {project.last_scan_status ?? "not run"}
                          </Badge>
                          {project.labels.map((label) => (
                            <Badge key={label}>{label}</Badge>
                          ))}
                        </div>
                        <h3 className="mt-3 break-words text-lg font-semibold text-ink">
                          {project.name}
                        </h3>
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
                          loading={isRunningThis}
                          disabled={run.isPending}
                          variant="secondary"
                          aria-label={
                            isRunningThis
                              ? `Running ${project.name}`
                              : `Run ${project.name}`
                          }
                        >
                          {isRunningThis ? (
                            <RefreshCw
                              className="motion-safe:animate-spin"
                              size={16}
                              aria-hidden
                            />
                          ) : (
                            <Play size={16} aria-hidden />
                          )}
                          {isRunningThis ? "Running" : "Run"}
                        </Button>
                        {project.last_scan_id ? (
                          <Link
                            href={`/scans/${project.last_scan_id}`}
                            className="inline-flex min-h-11 items-center justify-center gap-2 whitespace-nowrap rounded-product bg-signal px-4 py-2 text-sm font-semibold text-[var(--color-accent-ink)] hover:bg-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)] motion-safe:active:translate-y-px"
                          >
                            Scan detail <ArrowRight size={16} aria-hidden />
                          </Link>
                        ) : null}
                        <Link
                          href={`/projects/${project.id}`}
                          className={secondaryLinkClass}
                        >
                          Run history <GitCompareArrows size={16} aria-hidden />
                        </Link>
                      </div>
                    </div>
                  </Card>
                </li>
              );
            })}
          </ul>
        ) : null}
      </section>

      <details
        ref={createSectionRef}
        open={createExpanded}
        onToggle={(event) => setCreateOpen(event.currentTarget.open)}
        className="group scroll-mt-20 rounded-product border border-border bg-surface shadow-soft lg:scroll-mt-4"
      >
        <summary
          className={`${summaryClass} min-h-12 px-5 py-3 hover:bg-surface-muted`}
        >
          <h2 className="flex w-full items-center justify-between gap-3 text-lg font-semibold text-ink">
            New project
            <ChevronDown
              size={16}
              className="shrink-0 motion-safe:transition-transform motion-safe:group-open:rotate-180"
              aria-hidden
            />
          </h2>
        </summary>
        <div className="border-t border-border p-5">
          <p className="max-w-3xl text-sm leading-6 text-muted">
            A project stores the source, query, limit, cadence, and labels so
            you can rerun the same evidence search, inspect its scan record, and
            export only opportunities with visible source context.
          </p>
          <div className="mt-4 grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(260px,0.8fr)]">
            <form className="min-w-0 space-y-4" onSubmit={submitProject}>
              <div className="grid min-w-0 gap-4 sm:grid-cols-2">
                <label className="block min-w-0">
                  <span className="text-sm font-semibold text-muted">
                    Project name
                  </span>
                  <Input
                    ref={nameInputRef}
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    className="mt-2"
                    required
                  />
                </label>
                <label className="block min-w-0">
                  <span className="text-sm font-semibold text-muted">
                    Source
                  </span>
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
              {sourceType === "discourse" ? (
                <div className="min-w-0">
                  <label className="block min-w-0">
                    <span className="text-sm font-semibold text-muted">
                      Configured forum source
                    </span>
                    <Select
                      value={sourceId}
                      onChange={(event) => setSourceId(event.target.value)}
                      className="mt-2"
                      required
                      aria-busy={sources.isLoading || undefined}
                      aria-describedby={
                        discourseSourcesState === "ready"
                          ? undefined
                          : "discourse-source-help"
                      }
                    >
                      <option value="">
                        {discourseSourcesState === "loading"
                          ? "Loading configured forums…"
                          : discourseSourcesState === "error"
                            ? "Configured forums unavailable"
                            : "Choose a configured forum"}
                      </option>
                      {discourseSources.map((source) => (
                        <option key={source.id} value={source.id}>
                          {source.name}
                        </option>
                      ))}
                    </Select>
                  </label>
                  {discourseSourcesState === "loading" ? (
                    <p
                      id="discourse-source-help"
                      className="mt-1 text-xs leading-5 text-muted"
                    >
                      Loading configured forums from the Sources page.
                    </p>
                  ) : null}
                  {discourseSourcesState === "error" ? (
                    <div
                      id="discourse-source-help"
                      className="mt-2 flex flex-wrap items-center gap-2 text-xs leading-5 text-danger"
                    >
                      <span>
                        Could not load configured forums.{" "}
                        {errorMessage(sources.error)}
                      </span>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void sources.refetch()}
                        loading={sources.isFetching}
                        disabled={sources.isFetching}
                        aria-label="Retry loading configured forums"
                      >
                        <RefreshCw
                          size={15}
                          aria-hidden
                          className={
                            sources.isFetching
                              ? "motion-safe:animate-spin"
                              : undefined
                          }
                        />
                        {sources.isFetching ? "Retrying" : "Retry"}
                      </Button>
                    </div>
                  ) : null}
                  {discourseSourcesState === "empty" ? (
                    <p
                      id="discourse-source-help"
                      className="mt-1 text-xs leading-5 text-warning"
                    >
                      Add a public forum on the Sources page first. The API
                      checks exact-host authorization before saving or running
                      this project.{" "}
                      <Link
                        href="/sources"
                        className="inline-flex min-h-11 items-center gap-1 rounded-product font-semibold text-warning underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-warning"
                      >
                        Open Sources <ArrowRight size={14} aria-hidden />
                      </Link>
                    </p>
                  ) : null}
                </div>
              ) : null}
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
                  <span className="text-sm font-semibold text-muted">
                    Query
                  </span>
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
                  <span className="text-sm font-semibold text-muted">
                    Limit
                  </span>
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
                  <span className="text-sm font-semibold text-muted">
                    Hours
                  </span>
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
                    <RefreshCw
                      className="motion-safe:animate-spin"
                      size={16}
                      aria-hidden
                    />
                  ) : (
                    <Plus size={16} aria-hidden />
                  )}
                  {create.isPending ? "Saving project" : "Save project"}
                </Button>
              </div>
            </form>

            <div className="min-w-0 border-t border-border pt-4 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
              <p className="text-sm font-semibold text-ink">Selected source</p>
              {selectedSourcePreset ? (
                <div className="mt-2 text-sm leading-6">
                  <p className="text-ink">{selectedSourcePreset.credential}</p>
                  <p className="mt-1 text-muted">
                    {selectedSourcePreset.guidance}
                  </p>
                </div>
              ) : null}
              <p className="mt-3 border-t border-border pt-3 text-sm leading-6 text-muted">
                Operator-gated sources run from this browser only when the local
                token in the operator token panel above matches
                `OPERATOR_SCAN_TOKEN` on the API.
              </p>
            </div>
          </div>

          {create.error ? (
            <StateMessage
              tone="danger"
              title="Project was not saved"
              className="mt-4"
            >
              {errorMessage(create.error)}
            </StateMessage>
          ) : null}
          {create.data ? (
            <StateMessage
              tone="success"
              title="Research project saved"
              className="mt-4"
            >
              {create.data.name} is ready to run from the saved projects list
              above.
            </StateMessage>
          ) : null}
        </div>
      </details>
    </div>
  );
}
