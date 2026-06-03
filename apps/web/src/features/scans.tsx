"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Plus, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  PageHeader,
  StateMessage,
  TableShell,
} from "@/components/ui";

function errorMessage(error: unknown) {
  if (error instanceof Error) {
    try {
      // The local fetch wrapper puts backend JSON strings inside error.message
      const parsed = JSON.parse(error.message);
      if (parsed?.detail) {
        return typeof parsed.detail === "string"
          ? parsed.detail
          : JSON.stringify(parsed.detail);
      }
    } catch {
      // Fallback to the raw error text if it isn't JSON string formatted
      return error.message;
    }
  }
  return "The request failed.";
}

function statusTone(status: string): "green" | "amber" | "blue" | "red" {
  if (status === "completed") return "green";
  if (status === "failed") return "red";
  if (status === "running" || status === "queued") return "blue";
  return "amber";
}

function dateOrDash(value: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

export function Scans() {
  const queryClient = useQueryClient();
  const scans = useQuery({ queryKey: ["scans"], queryFn: api.scans });
  const create = useMutation({
    mutationFn: api.createScan,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scans"] }),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Scans"
        description="Review fixture and live-source ingestion runs with status, query, timing, and saved item counts."
        actions={
          <Button
            onClick={() =>
              create.mutate({
                source: "hackernews",
                query: "ask",
                limit: 30,
              })
            }
            loading={create.isPending}
            disabled={create.isPending}
          >
            {create.isPending ? (
              <RefreshCw className="animate-spin" size={16} />
            ) : (
              <Plus size={16} />
            )}
            {create.isPending ? "Running scan" : "Run public HN scan"}
          </Button>
        }
      />

      {create.error ? (
        <StateMessage tone="danger" title="Scan did not complete">
          {errorMessage(create.error)}
        </StateMessage>
      ) : null}
      {create.data ? (
        <StateMessage tone="success" title="Scan response received">
          {create.data.items_saved} saved from {create.data.items_found} found.
          Signals: {create.data.signals_detected}. Opportunities:{" "}
          {create.data.opportunities_created}. Status: {create.data.status}.
          {create.data.outcome_message ? ` ${create.data.outcome_message}` : ""}
        </StateMessage>
      ) : null}
      {scans.error ? (
        <StateMessage tone="danger" title="Could not load scan history">
          {errorMessage(scans.error)}
        </StateMessage>
      ) : null}

      <Card>
        <TableShell tableClassName="min-w-[760px]">
          <thead className="border-b border-border text-xs uppercase text-muted">
            <tr>
              <th className="py-3 pr-4">Status</th>
              <th className="py-3 pr-4">Source</th>
              <th className="py-3 pr-4">Query</th>
              <th className="py-3 pr-4">Started</th>
              <th className="py-3 pr-4">Finished</th>
              <th className="py-3 pr-4">Found</th>
              <th className="py-3 pr-4">Saved</th>
              <th className="py-3 pr-4">Signals</th>
              <th className="py-3 pr-4">Opps</th>
              <th className="py-3">Detail</th>
            </tr>
          </thead>
          <tbody>
            {scans.isLoading ? (
              <tr>
                <td colSpan={10} className="py-8 text-center text-sm text-muted">
                  Loading scan history...
                </td>
              </tr>
            ) : null}
            {!scans.isLoading && (scans.data ?? []).length === 0 ? (
              <tr>
                <td colSpan={10} className="py-8 text-center">
                  <div className="mx-auto max-w-md rounded-product border border-dashed border-border bg-surface-muted px-4 py-6">
                    <p className="text-sm font-semibold text-ink">
                      No scans recorded yet
                    </p>
                    <p className="mt-2 text-sm leading-6 text-muted">
                      Run fixture processing from the dashboard or start the
                      public Hacker News scan to create an auditable scan record.
                    </p>
                  </div>
                </td>
              </tr>
            ) : null}
            {!scans.isLoading &&
              (scans.data ?? []).map((scan) => (
                <tr key={scan.id} className="border-b border-border last:border-b-0">
                  <td className="py-3 pr-4">
                    <Badge tone={statusTone(scan.status)}>{scan.status}</Badge>
                  </td>
                  <td className="py-3 pr-4 text-ink">
                    {scan.source_name ?? scan.source_type ?? "-"}
                  </td>
                  <td className="max-w-sm break-words py-3 pr-4 text-muted">
                    {scan.query ?? "-"}
                  </td>
                  <td className="py-3 pr-4 text-muted">
                    {dateOrDash(scan.started_at)}
                  </td>
                  <td className="py-3 pr-4 text-muted">
                    {dateOrDash(scan.finished_at)}
                  </td>
                  <td className="py-3 pr-4 tabular-nums">{scan.items_found}</td>
                  <td className="py-3 pr-4 tabular-nums">{scan.items_saved}</td>
                  <td className="py-3 pr-4 tabular-nums">{scan.signals_detected}</td>
                  <td className="py-3 pr-4 tabular-nums">{scan.opportunities_created}</td>
                  <td className="py-3">
                    <Link
                      href={`/scans/${scan.id}`}
                      className="inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
                    >
                      Open <ArrowRight size={14} />
                    </Link>
                  </td>
                </tr>
              ))}
          </tbody>
        </TableShell>
      </Card>
    </div>
  );
}
