"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-error";
import { EVIDENCE_REVIEW_OPTIONS, formatPercentage } from "@/lib/review";
import type { EvaluationSlice } from "@/lib/types";
import {
  Card,
  EmptyState,
  MetricTile,
  PageHeader,
  StateMessage,
  TableShell,
} from "@/components/ui";

function BreakdownTable({
  title,
  rows,
}: {
  title: string;
  rows: Record<string, EvaluationSlice>;
}) {
  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <TableShell className="mt-4" tableClassName="min-w-[560px]">
        <thead>
          <tr className="border-b border-border text-xs uppercase text-muted">
            <th className="py-2 pr-3">Group</th>
            <th className="py-2 pr-3">Total</th>
            <th className="py-2 pr-3">Reviewed</th>
            <th className="py-2 pr-3">Coverage</th>
            <th className="py-2">Precision</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(rows).map(([name, row]) => (
            <tr
              key={name}
              className="border-b border-border last:border-0"
            >
              <td className="py-3 pr-3 font-medium">{name}</td>
              <td className="py-3 pr-3">{row.total_items}</td>
              <td className="py-3 pr-3">{row.reviewed_items}</td>
              <td className="py-3 pr-3">
                {formatPercentage(row.review_coverage)}
              </td>
              <td className="py-3">
                {row.precision_on_reviewed_positives === null
                  ? "Not defined"
                  : formatPercentage(row.precision_on_reviewed_positives)}
              </td>
            </tr>
          ))}
        </tbody>
      </TableShell>
    </Card>
  );
}

export function Evaluation() {
  const query = useQuery({
    queryKey: ["evaluation"],
    queryFn: api.evaluation,
  });
  if (query.isLoading) {
    return (
      <StateMessage tone="info" title="Loading evidence evaluation" />
    );
  }
  if (query.error) {
    return (
      <StateMessage tone="danger" title="Could not load evidence evaluation">
        {apiErrorMessage(query.error)}
      </StateMessage>
    );
  }
  const data = query.data;
  if (!data) {
    return (
      <StateMessage tone="danger" title="Evaluation response was empty" />
    );
  }
  const limits = (
    <StateMessage tone="warning" title="Evaluation limits">
      {data.selection_bias_warning} Recall and F1 are not reported because
      TaskSignal has no reviewed predicted-negative or undetected examples from
      which to estimate false negatives and recall.
    </StateMessage>
  );
  if (data.total_reviewable_items === 0) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Evidence evaluation"
          description="Selection-biased human review metrics for linked opportunity evidence."
        />
        <EmptyState
          title="No reviewable evidence yet"
          description="Process fixture or live data to generate opportunities and linked evidence."
        />
        {limits}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evidence evaluation"
        description="Selection-biased human review metrics for linked opportunity evidence."
      />
      {data.reviewed_items === 0 ? (
        <StateMessage tone="info" title="Evidence is ready for review">
          Open an opportunity and label its evidence to populate this report.
        </StateMessage>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <MetricTile label="Reviewable" value={data.total_reviewable_items} />
        <MetricTile label="Reviewed" value={data.reviewed_items} />
        <MetricTile
          label="Coverage"
          value={formatPercentage(data.review_coverage)}
        />
        <MetricTile
          label="Reviewed precision"
          value={
            data.precision_on_reviewed_positives === null
              ? "Not defined"
              : formatPercentage(data.precision_on_reviewed_positives)
          }
        />
        <MetricTile
          label="Legacy latest labels"
          value={data.unrecognized_latest_labels}
        />
      </div>
      <Card>
        <h2 className="text-lg font-semibold text-ink">Label counts</h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {EVIDENCE_REVIEW_OPTIONS.map((option) => (
            <div key={option.value}>
              <dt className="text-sm text-muted">{option.label}</dt>
              <dd className="text-2xl font-semibold text-ink">
                {data.label_counts[option.value]}
              </dd>
            </div>
          ))}
        </dl>
      </Card>
      <div className="grid gap-4 xl:grid-cols-2">
        <BreakdownTable title="By source" rows={data.by_source} />
        <BreakdownTable title="By signal type" rows={data.by_signal_type} />
      </div>
      {limits}
    </div>
  );
}
