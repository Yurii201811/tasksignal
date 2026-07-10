from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from math import ceil
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    ClusterItem,
    ItemSignal,
    Label,
    NormalizedItem,
    Opportunity,
)
from app.schemas.api import (
    EvaluationOut,
    EvaluationSliceOut,
    EvidenceLabelCountsOut,
    EvidenceReadinessChecksOut,
    EvidenceReadinessOut,
)
from app.services.evidence_review.types import (
    EvidenceReadinessLevel,
    EvidenceReviewLabel,
    EvidenceReviewSnapshot,
)
from app.services.ingestion.normalization import safe_source_url

CHECK_ORDER = (
    "enough_evidence",
    "source_diversity",
    "source_url_coverage",
    "human_review_coverage",
)
SELECTION_BIAS_WARNING = (
    "Metrics describe only manually reviewed evidence and may not represent "
    "all detected items."
)
ReviewableRecord = tuple[NormalizedItem, ItemSignal | None, EvidenceReviewSnapshot]


def _count_text(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def get_label_history(db: Session, item_id: UUID) -> list[Label]:
    return list(
        db.scalars(
            select(Label)
            .where(Label.item_id == item_id)
            .order_by(Label.created_at.desc(), Label.id.desc())
        )
    )


def get_review_snapshots(
    db: Session,
    item_ids: Collection[UUID],
) -> dict[UUID, EvidenceReviewSnapshot]:
    unique_ids = set(item_ids)
    if not unique_ids:
        return {}
    rows = list(
        db.scalars(
            select(Label)
            .where(Label.item_id.in_(unique_ids))
            .order_by(Label.created_at.desc(), Label.id.desc())
        )
    )
    latest: dict[UUID, Label] = {}
    history_counts: dict[UUID, int] = defaultdict(int)
    for row in rows:
        history_counts[row.item_id] += 1
        latest.setdefault(row.item_id, row)

    snapshots: dict[UUID, EvidenceReviewSnapshot] = {}
    for item_id in unique_ids:
        row = latest.get(item_id)
        recognized: EvidenceReviewLabel | None = None
        if row is not None:
            try:
                recognized = EvidenceReviewLabel(row.label)
            except ValueError:
                recognized = None
        snapshots[item_id] = EvidenceReviewSnapshot(
            latest_stored_label=row.label if row else None,
            review_label=recognized,
            review_note=row.user_note if row and recognized else None,
            reviewed_at=row.created_at if row and recognized else None,
            history_count=history_counts[item_id],
        )
    return snapshots


def calculate_evidence_readiness(
    items: Sequence[NormalizedItem],
    snapshots: Mapping[UUID, EvidenceReviewSnapshot],
) -> EvidenceReadinessOut:
    unique_items = {item.id: item for item in items}
    evidence_count = len(unique_items)
    source_count = len(
        {item.source.strip() for item in unique_items.values() if item.source.strip()}
    )
    safe_url_count = sum(
        bool(safe_source_url(item.url, fallback="")) for item in unique_items.values()
    )
    reviewed_count = sum(
        snapshots.get(item_id, EvidenceReviewSnapshot()).review_label is not None
        for item_id in unique_items
    )
    source_url_coverage = safe_url_count / evidence_count if evidence_count else 0.0
    human_review_coverage = reviewed_count / evidence_count if evidence_count else 0.0
    sensitive_risk = any(
        snapshots.get(item_id, EvidenceReviewSnapshot()).review_label
        == EvidenceReviewLabel.SENSITIVE_RISK
        for item_id in unique_items
    )
    checks = EvidenceReadinessChecksOut(
        enough_evidence=evidence_count >= 5,
        source_diversity=source_count >= 2,
        source_url_coverage=evidence_count > 0 and source_url_coverage >= 0.8,
        human_review_coverage=evidence_count > 0 and human_review_coverage >= 0.5,
    )
    check_values = checks.model_dump()
    passed_checks = [name for name in CHECK_ORDER if check_values[name]]
    gaps: list[str] = []
    if not checks.enough_evidence:
        remaining = 5 - evidence_count
        noun = _count_text(remaining, "item", "items")
        gaps.append(f"Collect {remaining} more evidence {noun}.")
    if not checks.source_diversity:
        remaining = 2 - source_count
        noun = _count_text(remaining, "source", "sources")
        gaps.append(f"Add evidence from {remaining} more {noun}.")
    if not checks.source_url_coverage:
        gaps.append("Increase safe source URL coverage to at least 80%.")
    if not checks.human_review_coverage:
        remaining = max(1, ceil(evidence_count * 0.5) - reviewed_count)
        noun = _count_text(remaining, "item", "items")
        gaps.append(f"Review {remaining} more evidence {noun}.")
    if sensitive_risk:
        gaps.append("Resolve or exclude evidence marked sensitive risk before advancing.")

    passed_count = len(passed_checks)
    if sensitive_risk:
        level = EvidenceReadinessLevel.WEAK
    elif passed_count == len(CHECK_ORDER):
        level = EvidenceReadinessLevel.STRONG
    elif passed_count >= 2:
        level = EvidenceReadinessLevel.MEDIUM
    else:
        level = EvidenceReadinessLevel.WEAK

    return EvidenceReadinessOut(
        level=level,
        evidence_count=evidence_count,
        source_count=source_count,
        safe_url_count=safe_url_count,
        reviewed_count=reviewed_count,
        source_url_coverage=source_url_coverage,
        human_review_coverage=human_review_coverage,
        checks=checks,
        passed_checks=passed_checks,
        gaps=gaps,
    )


def _label_counts(records: Sequence[ReviewableRecord]) -> EvidenceLabelCountsOut:
    counts = {label.value: 0 for label in EvidenceReviewLabel}
    for _item, _signal, snapshot in records:
        if snapshot.review_label is not None:
            counts[snapshot.review_label.value] += 1
    return EvidenceLabelCountsOut(**counts)


def _evaluation_slice(records: Sequence[ReviewableRecord]) -> EvaluationSliceOut:
    total = len(records)
    reviewed = sum(snapshot.review_label is not None for _, _, snapshot in records)
    counts = _label_counts(records)
    precision_denominator = counts.true_signal + counts.false_positive
    precision = (
        counts.true_signal / precision_denominator if precision_denominator else None
    )
    return EvaluationSliceOut(
        total_items=total,
        reviewed_items=reviewed,
        review_coverage=reviewed / total if total else 0.0,
        label_counts=counts,
        precision_on_reviewed_positives=precision,
    )


def evaluation_summary(db: Session) -> EvaluationOut:
    rows = db.execute(
        select(NormalizedItem, ItemSignal)
        .join(ClusterItem, ClusterItem.item_id == NormalizedItem.id)
        .join(Opportunity, Opportunity.cluster_id == ClusterItem.cluster_id)
        .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id, isouter=True)
    ).all()
    deduplicated: dict[UUID, tuple[NormalizedItem, ItemSignal | None]] = {}
    for item, signal in rows:
        deduplicated.setdefault(item.id, (item, signal))
    snapshots = get_review_snapshots(db, deduplicated)
    records: list[ReviewableRecord] = [
        (item, signal, snapshots.get(item_id, EvidenceReviewSnapshot()))
        for item_id, (item, signal) in deduplicated.items()
    ]
    overall = _evaluation_slice(records)
    by_source_records: dict[str, list[ReviewableRecord]] = defaultdict(list)
    by_signal_records: dict[str, list[ReviewableRecord]] = defaultdict(list)
    for record in records:
        item, signal, _snapshot = record
        by_source_records[item.source.strip() or "unknown"].append(record)
        signal_type = signal.signal_type.strip() if signal and signal.signal_type else ""
        by_signal_records[signal_type or "unknown"].append(record)

    return EvaluationOut(
        total_reviewable_items=overall.total_items,
        reviewed_items=overall.reviewed_items,
        review_coverage=overall.review_coverage,
        label_counts=overall.label_counts,
        unrecognized_latest_labels=sum(
            snapshot.latest_stored_label is not None and snapshot.review_label is None
            for _, _, snapshot in records
        ),
        precision_on_reviewed_positives=overall.precision_on_reviewed_positives,
        by_source={
            key: _evaluation_slice(by_source_records[key])
            for key in sorted(by_source_records)
        },
        by_signal_type={
            key: _evaluation_slice(by_signal_records[key])
            for key in sorted(by_signal_records)
        },
        selection_bias_warning=SELECTION_BIAS_WARNING,
    )
