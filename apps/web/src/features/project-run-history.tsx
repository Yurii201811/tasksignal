"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, GitCompareArrows } from "lucide-react";
import { api } from "@/lib/api";
import type { RunDeltaCounts } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  PageHeader,
  StateMessage,
  TableShell,
} from "@/components/ui";

function errorMessage(error: unknown) {
  if (!(error instanceof Error)) return "The request failed.";
  try {
    const detail = JSON.parse(error.message)?.detail;
    return typeof detail === "string" ? detail : error.message;
  } catch {
    return error.message;
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function DeltaCounts({ counts }: { counts: RunDeltaCounts }) {
  const values = [
    ["New", counts.new],
    ["Seen before", counts.seen_before],
    ["Updated", counts.updated],
    ["Unchanged", counts.unchanged],
    ["Not observed this run", counts.not_observed_this_run],
  ] as const;
  return (
    <dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {values.map(([label, value]) => (
        <div key={label} className="border-t border-border pt-3">
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
            {label}
          </dt>
          <dd className="mt-1 text-2xl font-semibold tabular-nums text-ink">
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ProjectRunHistory({ id }: { id: string }) {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const project = useQuery({
    queryKey: ["research-project", id],
    queryFn: () => api.researchProject(id),
  });
  const runs = useQuery({
    queryKey: ["research-project-runs", id],
    queryFn: () => api.researchProjectRuns(id),
  });
  const delta = useQuery({
    queryKey: ["research-project-run-delta", id, selectedRunId],
    queryFn: () => api.researchProjectRunDelta(id, selectedRunId as string),
    enabled: selectedRunId !== null,
  });
  const error = project.error ?? runs.error;

  return (
    <div className="space-y-6">
      <PageHeader
        title={project.data?.name ?? "Project run history"}
        description="Immutable run snapshots show what the connector observed and how that evidence changed from the previous complete run."
        actions={
          <Link
            href="/projects"
            className="inline-flex min-h-11 items-center gap-2 rounded-product border border-border-strong bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
          >
            <ArrowLeft size={16} aria-hidden /> Projects
          </Link>
        }
      />

      {error ? (
        <StateMessage tone="danger" title="Could not load run history">
          {errorMessage(error)}
        </StateMessage>
      ) : null}
      {project.isLoading || runs.isLoading ? (
        <StateMessage tone="info" title="Loading immutable runs">
          Reading this project&apos;s tracked and legacy scan lineage.
        </StateMessage>
      ) : null}

      {!runs.isLoading && (runs.data ?? []).length === 0 ? (
        <StateMessage tone="warning" title="No runs yet">
          Run the project once to create its first auditable snapshot.
        </StateMessage>
      ) : null}

      {(runs.data ?? []).length > 0 ? (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-ink">Run ledger</h2>
              <p className="mt-1 text-sm leading-6 text-muted">
                Source, query, limit, counts, and lineage are recorded per run.
              </p>
            </div>
            <Badge>{runs.data?.length ?? 0} snapshots</Badge>
          </div>
          <TableShell
            className="mt-4"
            label="Project run history"
            caption="Immutable project research runs and comparison actions"
            tableClassName="min-w-[860px]"
          >
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="py-3 pr-4">Run</th>
                <th className="py-3 pr-4">Started</th>
                <th className="py-3 pr-4">Source snapshot</th>
                <th className="py-3 pr-4">Observed / saved</th>
                <th className="py-3 pr-4">Generated</th>
                <th className="py-3 text-right">Delta</th>
              </tr>
            </thead>
            <tbody>
              {(runs.data ?? []).map((run) => (
                <tr
                  key={run.id}
                  className="border-b border-border last:border-0"
                >
                  <td className="py-4 pr-4 align-top">
                    <p className="font-semibold text-ink">
                      {run.sequence === null
                        ? "Legacy run"
                        : `Run ${run.sequence}`}
                    </p>
                    <Badge
                      tone={
                        run.lineage_status === "complete"
                          ? "green"
                          : run.lineage_status === "incomplete"
                            ? "amber"
                            : "slate"
                      }
                    >
                      {run.lineage_status === "untracked"
                        ? "Lineage untracked"
                        : `Lineage ${run.lineage_status}`}
                    </Badge>
                  </td>
                  <td className="py-4 pr-4 align-top text-muted">
                    {formatDate(run.started_at)}
                  </td>
                  <td className="py-4 pr-4 align-top text-muted">
                    <p>{run.source_type ?? "Unknown source"}</p>
                    <p className="mt-1 max-w-56 break-words font-mono text-xs">
                      {run.query || "No query"} · limit{" "}
                      {run.requested_limit ?? "unknown"}
                    </p>
                  </td>
                  <td className="py-4 pr-4 align-top tabular-nums text-muted">
                    {run.items_found} / {run.items_saved}
                  </td>
                  <td className="py-4 pr-4 align-top text-muted">
                    {run.clusters_created} clusters ·{" "}
                    {run.opportunities_created} opportunities
                  </td>
                  <td className="py-4 text-right align-top">
                    {run.lineage_status === "complete" ? (
                      <Button
                        size="sm"
                        variant={
                          selectedRunId === run.id ? "primary" : "secondary"
                        }
                        onClick={() => setSelectedRunId(run.id)}
                      >
                        <GitCompareArrows size={15} aria-hidden /> Compare run{" "}
                        {run.sequence}
                      </Button>
                    ) : (
                      <span className="text-xs text-muted">
                        Not safely comparable
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </Card>
      ) : null}

      {delta.isLoading ? (
        <StateMessage tone="info" title="Calculating exact delta">
          Comparing stable identities with the previous complete run.
        </StateMessage>
      ) : null}
      {delta.error ? (
        <StateMessage tone="warning" title="This run cannot be compared">
          {errorMessage(delta.error)}
        </StateMessage>
      ) : null}
      {delta.data ? (
        <section className="space-y-4" aria-labelledby="run-delta-heading">
          <Card variant="muted">
            <h2
              id="run-delta-heading"
              className="text-lg font-semibold text-ink"
            >
              Run {delta.data.sequence} delta
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              “Not observed this run” means only that a stable identity was
              absent from this observation. Its absence never means deletion or
              resolution.
            </p>
          </Card>
          <Card>
            <h3 className="font-semibold text-ink">Evidence changes</h3>
            <DeltaCounts counts={delta.data.evidence_changes} />
          </Card>
          <Card>
            <h3 className="font-semibold text-ink">Signal changes</h3>
            <DeltaCounts counts={delta.data.signal_changes} />
          </Card>
          {delta.data.opportunity_changes ? (
            <Card>
              <h3 className="font-semibold text-ink">
                Opportunity thread changes
              </h3>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["New", delta.data.opportunity_changes.new],
                  ["Updated", delta.data.opportunity_changes.updated],
                  ["Unchanged", delta.data.opportunity_changes.unchanged],
                  [
                    "Not observed this run",
                    delta.data.opportunity_changes.not_observed_this_run,
                  ],
                ].map(([label, value]) => (
                  <div
                    key={String(label)}
                    className="border-t border-border pt-3"
                  >
                    <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                      {label}
                    </dt>
                    <dd className="mt-1 text-2xl font-semibold tabular-nums text-ink">
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
            </Card>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
