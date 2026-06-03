"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Play, Plus, RefreshCw } from "lucide-react";
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

const sourceOptions = [
  { value: "hackernews", label: "Hacker News", defaultQuery: "ask" },
  { value: "fixture", label: "Fixture files", defaultQuery: "" },
  { value: "github", label: "GitHub Issues", defaultQuery: "label:bug" },
  {
    value: "reddit",
    label: "Reddit",
    defaultQuery: "manual workflow automation",
  },
  {
    value: "stackexchange",
    label: "Stack Exchange",
    defaultQuery: "automation",
  },
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

export function ResearchProjects() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("Track CI/CD pain");
  const [description, setDescription] = useState(
    "Find repeated complaints that could become a focused developer-tool MVP.",
  );
  const [sourceType, setSourceType] = useState("hackernews");
  const [query, setQuery] = useState("ask");
  const [limit, setLimit] = useState(30);
  const [labels, setLabels] = useState("ci, developer-tools");
  const [operatorToken, setOperatorToken] = useState("");
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

  useEffect(() => {
    setOperatorToken(
      window.localStorage.getItem("tasksignal.operatorToken") ?? "",
    );
  }, []);

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
      cadence: "manual",
      labels: labels
        .split(",")
        .map((label) => label.trim())
        .filter(Boolean),
      enabled: true,
    });
  }

  const latestScan = scans.data?.[0];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Research projects"
        description="Save source and query workflows, rerun them, and turn the strongest evidence into Codex task packs."
      />

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
            <Button
              type="submit"
              loading={create.isPending}
              disabled={create.isPending}
            >
              {create.isPending ? (
                <RefreshCw className="animate-spin" size={16} />
              ) : (
                <Plus size={16} />
              )}
              {create.isPending ? "Saving project" : "Save project"}
            </Button>
          </form>

          <div className="min-w-0 rounded-product border border-border bg-surface-muted p-4">
            <p className="text-sm font-semibold text-ink">Operator token</p>
            <p className="mt-2 text-sm leading-6 text-muted">
              Public sources run without this. Credentialed GitHub, Reddit, and
              Stack Exchange browser runs require `OPERATOR_SCAN_TOKEN` on the
              API and the matching local token here.
            </p>
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
          <StateMessage tone="warning" title="No saved research projects yet">
            Save a source and query above, then run it whenever you want fresh
            evidence.
          </StateMessage>
        ) : null}
        {(projects.data ?? []).map((project) => (
          <Card key={project.id}>
            <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="blue">{project.source_type}</Badge>
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
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button
                  onClick={() => run.mutate(project)}
                  loading={run.isPending}
                  disabled={run.isPending}
                  variant="secondary"
                >
                  {run.isPending ? (
                    <RefreshCw className="animate-spin" size={16} />
                  ) : (
                    <Play size={16} />
                  )}
                  {run.isPending ? "Running" : "Run"}
                </Button>
                {project.last_scan_id ? (
                  <Link
                    href={`/scans/${project.last_scan_id}`}
                    className="inline-flex min-h-11 items-center justify-center gap-2 rounded-product bg-signal px-4 py-2 text-sm font-semibold text-[color-mix(in_srgb,var(--ts-surface)_96%,transparent)] hover:bg-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
                  >
                    Scan detail <ArrowRight size={16} />
                  </Link>
                ) : null}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
