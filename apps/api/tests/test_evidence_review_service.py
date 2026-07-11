from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select

from app.models.all_models import ClusterItem, Label, NormalizedItem, Opportunity
from app.services.evidence_review.service import (
    calculate_evidence_readiness,
    evaluation_summary,
    get_review_snapshots,
)
from app.services.evidence_review.types import EvidenceReviewLabel, EvidenceReviewSnapshot
from app.workers.demo_pipeline import process_demo


def test_latest_unrecognized_label_does_not_fall_back(db_session) -> None:
    process_demo(db_session)
    item_id = db_session.scalar(select(NormalizedItem.id))
    assert item_id is not None
    timestamp = datetime(2026, 7, 9, tzinfo=UTC)
    db_session.add_all(
        [
            Label(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                item_id=item_id,
                label="true_signal",
                user_note="recognized",
                version=1,
                created_at=timestamp,
            ),
            Label(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                item_id=item_id,
                label="legacy_label",
                user_note="legacy newest",
                version=2,
                created_at=timestamp,
            ),
        ]
    )
    db_session.commit()

    snapshot = get_review_snapshots(db_session, [item_id])[item_id]

    assert snapshot.latest_stored_label == "legacy_label"
    assert snapshot.review_label is None
    assert snapshot.review_note is None
    assert snapshot.reviewed_at is None
    assert snapshot.history_count == 2


def test_readiness_uses_fixed_checks_and_sensitive_override() -> None:
    items = [
        SimpleNamespace(id=uuid4(), source="github", url="https://example.test/1"),
        SimpleNamespace(id=uuid4(), source="github", url="https://example.test/2"),
        SimpleNamespace(id=uuid4(), source="hackernews", url="https://example.test/3"),
        SimpleNamespace(id=uuid4(), source="hackernews", url="https://example.test/4"),
        SimpleNamespace(id=uuid4(), source="hackernews", url="javascript:alert(1)"),
    ]
    snapshots = {
        items[0].id: EvidenceReviewSnapshot(
            latest_stored_label="true_signal",
            review_label=EvidenceReviewLabel.TRUE_SIGNAL,
            history_count=1,
        ),
        items[1].id: EvidenceReviewSnapshot(
            latest_stored_label="true_signal",
            review_label=EvidenceReviewLabel.TRUE_SIGNAL,
            history_count=1,
        ),
        items[2].id: EvidenceReviewSnapshot(
            latest_stored_label="sensitive_risk",
            review_label=EvidenceReviewLabel.SENSITIVE_RISK,
            history_count=1,
        ),
    }

    readiness = calculate_evidence_readiness(items, snapshots)

    assert readiness.evidence_count == 5
    assert readiness.source_count == 2
    assert readiness.safe_url_count == 4
    assert readiness.reviewed_count == 3
    assert readiness.source_url_coverage == 0.8
    assert readiness.human_review_coverage == 0.6
    assert all(readiness.checks.model_dump().values())
    assert readiness.level == "weak"
    assert readiness.gaps == [
        "Resolve or exclude evidence marked sensitive risk before advancing."
    ]


def readiness_items(
    count: int,
    sources: tuple[str, ...],
    safe_url_count: int,
) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            id=uuid4(),
            source=sources[index % len(sources)],
            url=(
                f"https://example.test/{index}"
                if index < safe_url_count
                else "javascript:alert(1)"
            ),
        )
        for index in range(count)
    ]


def test_readiness_levels_and_deterministic_gap_templates() -> None:
    strong_items = readiness_items(6, ("github", "hackernews"), 6)
    strong_snapshots = {
        item.id: EvidenceReviewSnapshot(
            latest_stored_label="true_signal",
            review_label=EvidenceReviewLabel.TRUE_SIGNAL,
            history_count=1,
        )
        for item in strong_items[:3]
    }
    strong = calculate_evidence_readiness(strong_items, strong_snapshots)
    assert strong.level == "strong"
    assert strong.passed_checks == [
        "enough_evidence",
        "source_diversity",
        "source_url_coverage",
        "human_review_coverage",
    ]
    assert strong.gaps == []

    medium_items = readiness_items(5, ("github",), 4)
    medium = calculate_evidence_readiness(medium_items, {})
    assert medium.level == "medium"
    assert medium.passed_checks == ["enough_evidence", "source_url_coverage"]
    assert medium.gaps == [
        "Add evidence from 1 more source.",
        "Review 3 more evidence items.",
    ]

    weak_items = readiness_items(1, ("github",), 0)
    weak = calculate_evidence_readiness(weak_items, {})
    assert weak.level == "weak"
    assert weak.passed_checks == []
    assert weak.gaps == [
        "Collect 4 more evidence items.",
        "Add evidence from 1 more source.",
        "Increase safe source URL coverage to at least 80%.",
        "Review 1 more evidence item.",
    ]


def test_empty_evaluation_is_zeroed(db_session) -> None:
    summary = evaluation_summary(db_session)

    assert summary.total_reviewable_items == 0
    assert summary.reviewed_items == 0
    assert summary.review_coverage == 0.0
    assert summary.label_counts.model_dump() == {
        label.value: 0 for label in EvidenceReviewLabel
    }
    assert summary.unrecognized_latest_labels == 0
    assert summary.precision_on_reviewed_positives is None
    assert summary.by_source == {}
    assert summary.by_signal_type == {}


def test_evaluation_counts_reviewed_items_and_precision_without_duplicates(db_session) -> None:
    process_demo(db_session)
    opportunity = db_session.scalar(
        select(Opportunity).order_by(Opportunity.opportunity_score.desc())
    )
    assert opportunity is not None
    item_ids = list(
        db_session.scalars(
            select(ClusterItem.item_id).where(
                ClusterItem.cluster_id == opportunity.cluster_id
            )
        )
    )
    assert len(item_ids) >= 2
    baseline = evaluation_summary(db_session)
    db_session.add(
        Opportunity(
            **{
                column.name: getattr(opportunity, column.name)
                for column in Opportunity.__table__.columns
                if column.name != "id"
            }
        )
    )
    db_session.add_all(
        [
            Label(item_id=item_ids[0], label="true_signal", user_note=None),
            Label(item_id=item_ids[1], label="false_positive", user_note=None),
        ]
    )
    db_session.commit()

    summary = evaluation_summary(db_session)

    assert summary.total_reviewable_items == baseline.total_reviewable_items
    assert summary.reviewed_items == 2
    assert summary.label_counts.true_signal == 1
    assert summary.label_counts.false_positive == 1
    assert summary.precision_on_reviewed_positives == 0.5
    assert summary.unrecognized_latest_labels == 0
    assert list(summary.by_source) == sorted(summary.by_source)
    assert list(summary.by_signal_type) == sorted(summary.by_signal_type)
    assert sum(row.total_items for row in summary.by_source.values()) == (
        summary.total_reviewable_items
    )
    assert sum(row.total_items for row in summary.by_signal_type.values()) == (
        summary.total_reviewable_items
    )
    assert summary.selection_bias_warning == (
        "Metrics describe only manually reviewed evidence and may not represent "
        "all detected items."
    )
