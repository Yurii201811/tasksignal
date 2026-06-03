"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Database,
  FileWarning,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  Badge,
  Card,
  MetricTile,
  PageHeader,
  StateMessage,
  TableShell,
} from "@/components/ui";
import type { Scan } from "@/lib/types";

function statusTone(status: string): "green" | "amber" | "blue" | "red" {
  if (status === "completed") return "green";
  if (status === "failed") return "red";
  if (status === "running" || status === "queued") return "blue";
  return "amber";
}

function dateOrDash(value: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function durationLabel(scan: Scan) {
  if (!scan.finished_at) {
    return "In progress";
  }

  const started = new Date(scan.started_at).getTime();
  const finished = new Date(scan.finished_at).getTime();
  if (Number.isNaN(started) || Number.isNaN(finished) || finished < started) {
    return "-";
  }

  const seconds = Math.round((finished - started) / 1000);
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m ${remainder}s`;
}

function savedRate(scan: Scan) {
  if (scan.items_found <= 0) {
    return "0%";
  }
  return `${Math.round((scan.items_saved / scan.items_found) * 100)}%`;
}

function completedTone(scan: Scan): "success" | "warning" {
  return scan.opportunities_created > 0 ? "success" : "warning";
}

function parsedErrorDetail(error: unknown) {
  if (!(error instanceof Error)) {
    return "The request failed.";
  }

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

  return error.message;
}

function statusMessage(scan: Scan) {
  if (scan.status === "completed") {
    const hasOpportunities = scan.opportunities_created > 0;
    return (
      <StateMessage
        tone={completedTone(scan)}
        title={hasOpportunities ? "Scan completed with opportunities" : "Scan completed without opportunities"}
      >
        This run finished and saved {scan.items_saved} of {scan.items_found} found
        public-source records. It detected {scan.signals_detected} signals and
        generated {scan.opportunities_created} opportunities.
        {scan.outcome_message ? ` ${scan.outcome_message}` : ""}
      </StateMessage>
    );
  }

  if (scan.status === "failed") {
    return (
      <StateMessage tone="danger" title="Scan failed with a redacted message">
        {scan.error_message || "No error message was stored for this scan."}
      </StateMessage>
    );
  }

  if (scan.status === "running" || scan.status === "queued") {
    return (
      <StateMessage tone="info" title="Scan is still running">
        Refresh the scan list after the connector finishes to review saved item
        counts and any error message.
      </StateMessage>
    );
  }

  return (
    <StateMessage tone="warning" title="Scan status needs review">
      This scan has status {scan.status}. Check the stored timestamps and item
      counts before treating it as complete.
    </StateMessage>
  );
}

function DetailRow({ label, value }: { label: string; value: string | number | null }) {
  return (
    <tr className="border-b border-border last:border-b-0">
      <th className="w-48 py-3 pr-4 text-sm font-semibold text-muted">{label}</th>
      <td className="break-words py-3 text-sm text-ink">{value ?? "-"}</td>
    </tr>
  );
}

export function ScanDetail({ id }: { id: string }) {
  const { data, error, isError, isLoading } = useQuery({
    queryKey: ["scan", id],
    queryFn: () => api.scan(id),
    retry: false,
  });

  if (isLoading) {
    return (
      <StateMessage tone="info" title="Loading scan">
        Fetching source, query, status, timing, and saved item counts.
      </StateMessage>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <Link
          href="/scans"
          className="inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
        >
          <ArrowLeft size={15} /> Back to scans
        </Link>
        <StateMessage tone="warning" title="Scan not found">
          {parsedErrorDetail(error)}
        </StateMessage>
      </div>
    );
  }

  if (!data) {
    return (
      <StateMessage tone="warning" title="Scan not found">
        Return to the scans list and open an existing ingestion run.
      </StateMessage>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        href="/scans"
        className="inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
      >
        <ArrowLeft size={15} /> Back to scans
      </Link>

      <PageHeader
        title="Scan detail"
        description="Inspect one ingestion run with source, query, timing, saved item counts, signal counts, generated opportunities, and any redacted connector error."
        actions={<Badge tone={statusTone(data.status)}>{data.status}</Badge>}
      />

      {statusMessage(data)}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile
          label="Found"
          value={data.items_found}
          hint="Connector records returned"
        />
        <MetricTile
          label="Saved"
          value={data.items_saved}
          hint={`${savedRate(data)} saved rate`}
        />
        <MetricTile
          label="Signals"
          value={data.signals_detected}
          hint="Detected problem signals"
        />
        <MetricTile
          label="Opportunities"
          value={data.opportunities_created}
          hint="Generated from this scan"
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="Duration" value={durationLabel(data)} hint="Started to finished" />
        <MetricTile
          label="Source"
          value={data.source_name ?? data.source_type ?? "-"}
          hint="Configured public source"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <div className="mb-4 flex items-center gap-2">
            <Database className="h-5 w-5 text-signal" aria-hidden />
            <h2 className="text-lg font-semibold text-ink">Run metadata</h2>
          </div>
          <TableShell>
            <tbody>
              <DetailRow label="Scan ID" value={data.id} />
              <DetailRow label="Source type" value={data.source_type} />
              <DetailRow label="Source name" value={data.source_name} />
              <DetailRow label="Query" value={data.query || "-"} />
              <DetailRow label="Started" value={dateOrDash(data.started_at)} />
              <DetailRow label="Finished" value={dateOrDash(data.finished_at)} />
              <DetailRow label="Items found" value={data.items_found} />
              <DetailRow label="Items saved" value={data.items_saved} />
              <DetailRow label="Signals detected" value={data.signals_detected} />
              <DetailRow label="Clusters created" value={data.clusters_created} />
              <DetailRow label="Opportunities created" value={data.opportunities_created} />
              <DetailRow label="Outcome" value={data.outcome_message} />
            </tbody>
          </TableShell>
        </Card>

        <div className="space-y-4">
          <Card variant={data.status === "failed" ? "danger" : "muted"}>
            <div className="flex items-start gap-3">
              {data.status === "failed" ? (
                <FileWarning className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden />
              ) : data.status === "completed" ? (
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden />
              ) : (
                <Clock className="mt-0.5 h-5 w-5 shrink-0 text-info" aria-hidden />
              )}
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-ink">Operational state</h2>
                <p className="mt-1 text-sm leading-6 text-muted">
                  Completed, zero-opportunity, and failed scans use the same
                  detail surface so reviewers can compare connector behavior
                  without inspecting raw logs.
                </p>
              </div>
            </div>
          </Card>

          <Card variant="muted">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden />
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-ink">Credential safety</h2>
                <p className="mt-1 text-sm leading-6 text-muted">
                  The page only renders API scan fields. Credential values,
                  tokens, raw connector payloads, and author identifiers are not
                  displayed.
                </p>
              </div>
            </div>
          </Card>

          {data.error_message ? (
            <Card variant="danger">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden />
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold text-danger">Error message</h2>
                  <p className="mt-1 break-words text-sm leading-6 text-muted">
                    {data.error_message}
                  </p>
                </div>
              </div>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
