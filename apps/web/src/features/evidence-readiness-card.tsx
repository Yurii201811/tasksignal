import { Badge, Card } from "@/components/ui";
import {
  formatPercentage,
  READINESS_CHECKS,
  READINESS_TONES,
} from "@/lib/review";
import type { EvidenceReadiness } from "@/lib/types";

export function EvidenceReadinessCard({
  readiness,
}: {
  readiness: EvidenceReadiness;
}) {
  return (
    <Card variant="muted">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">
            Evidence readiness
          </h2>
          <p className="mt-1 text-sm text-muted">
            Review preparation, not market validation.
          </p>
        </div>
        <Badge tone={READINESS_TONES[readiness.level]}>
          {readiness.level}
        </Badge>
      </div>
      <p className="mt-3 text-sm text-muted">
        {readiness.evidence_count} evidence · {readiness.source_count} sources ·{" "}
        {readiness.safe_url_count} safe URLs · {readiness.reviewed_count} reviewed
      </p>
      <p className="mt-1 text-xs text-muted">
        URL coverage {formatPercentage(readiness.source_url_coverage)} · Human
        review {formatPercentage(readiness.human_review_coverage)}
      </p>
      <ul className="mt-4 grid gap-2 text-sm">
        {READINESS_CHECKS.map(({ key, label }) => (
          <li key={key} className="flex justify-between gap-3">
            <span>{label}</span>
            <span>{readiness.checks[key] ? "Passed" : "Needs work"}</span>
          </li>
        ))}
      </ul>
      {readiness.gaps.length ? (
        <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-muted">
          {readiness.gaps.map((gap) => (
            <li key={gap}>{gap}</li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
