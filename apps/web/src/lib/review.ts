import type {
  EvidenceReadinessCheck,
  EvidenceReadinessLevel,
  EvidenceReviewLabel,
  ReviewState,
} from "./types";

type BadgeTone = "slate" | "green" | "amber" | "blue" | "red";

export const REVIEW_STATE_OPTIONS: {
  value: ReviewState;
  label: string;
  tone: BadgeTone;
}[] = [
  { value: "new", label: "New", tone: "slate" },
  { value: "needs_more_evidence", label: "Needs more evidence", tone: "amber" },
  { value: "promising", label: "Promising", tone: "blue" },
  { value: "rejected", label: "Rejected", tone: "red" },
  { value: "duplicate", label: "Duplicate", tone: "slate" },
  { value: "build_candidate", label: "Build candidate", tone: "green" },
];

export const EVIDENCE_REVIEW_OPTIONS: {
  value: EvidenceReviewLabel;
  label: string;
}[] = [
  { value: "true_signal", label: "True signal" },
  { value: "false_positive", label: "False positive" },
  { value: "unclear", label: "Unclear" },
  { value: "duplicate", label: "Duplicate" },
  { value: "not_actionable", label: "Not actionable" },
  { value: "sensitive_risk", label: "Sensitive risk" },
];

export const READINESS_CHECKS: { key: EvidenceReadinessCheck; label: string }[] = [
  { key: "enough_evidence", label: "Enough evidence" },
  { key: "source_diversity", label: "Source diversity" },
  { key: "source_url_coverage", label: "Safe source URL coverage" },
  { key: "human_review_coverage", label: "Human review coverage" },
];

export const READINESS_TONES: Record<EvidenceReadinessLevel, BadgeTone> = {
  weak: "red",
  medium: "amber",
  strong: "green",
};

export function reviewStateOption(state: ReviewState) {
  return REVIEW_STATE_OPTIONS.find((option) => option.value === state)!;
}

export function evidenceReviewLabel(label: EvidenceReviewLabel) {
  return EVIDENCE_REVIEW_OPTIONS.find((option) => option.value === label)!.label;
}

export function formatPercentage(value: number) {
  return `${Math.round(value * 100)}%`;
}
