from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReviewState(StrEnum):
    NEW = "new"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    PROMISING = "promising"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    BUILD_CANDIDATE = "build_candidate"


class EvidenceReviewLabel(StrEnum):
    TRUE_SIGNAL = "true_signal"
    FALSE_POSITIVE = "false_positive"
    UNCLEAR = "unclear"
    DUPLICATE = "duplicate"
    NOT_ACTIONABLE = "not_actionable"
    SENSITIVE_RISK = "sensitive_risk"


class EvidenceReadinessLevel(StrEnum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


@dataclass(frozen=True)
class EvidenceReviewSnapshot:
    latest_stored_label: str | None = None
    review_label: EvidenceReviewLabel | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None
    history_count: int = 0
