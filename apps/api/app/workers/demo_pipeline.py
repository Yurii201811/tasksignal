from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.all_models import (
    Cluster,
    ClusterItem,
    ItemEmbedding,
    ItemSignal,
    Label,
    NormalizedItem,
    Opportunity,
    RawItem,
    ResearchProject,
    ResearchProjectRun,
    ScanItem,
    ScanJob,
    Source,
)
from app.services.ingestion.connectors import FixtureConnector
from app.workers.scan_pipeline import (
    SCAN_WRITE_LOCK,
    acquire_database_scan_write_lock_with_retry,
    process_fetched_items,
    scan_outcome_message,
)


def reset_demo_data(db: Session) -> None:
    with SCAN_WRITE_LOCK:
        acquire_database_scan_write_lock_with_retry(db)
        db.execute(
            update(ResearchProject).values(
                last_scan_id=None,
                last_run_at=None,
                run_count=0,
            )
        )
        for model in [
            Label,
            Opportunity,
            ClusterItem,
            Cluster,
            ScanItem,
            ResearchProjectRun,
            ItemEmbedding,
            ItemSignal,
            NormalizedItem,
            RawItem,
            ScanJob,
        ]:
            db.execute(delete(model))
        db.commit()


def ensure_sources(db: Session) -> None:
    existing = {source.type for source in db.scalars(select(Source)).all()}
    defaults = [
        ("Fixture files", "fixture"),
        ("Reddit", "reddit"),
        ("Hacker News", "hackernews"),
        ("GitHub Issues", "github"),
        ("Stack Exchange", "stackexchange"),
    ]
    for name, source_type in defaults:
        if source_type not in existing:
            db.add(
                Source(
                    name=name, type=source_type, config_json={}, enabled=source_type == "fixture"
                )
            )
    db.commit()


def process_demo(db: Session, reset: bool = False) -> dict[str, int]:
    if reset:
        reset_demo_data(db)
    ensure_sources(db)
    fixture_source_id = db.scalar(select(Source.id).where(Source.type == "fixture"))
    job = ScanJob(source_id=fixture_source_id, status="running", query="fixture demo")
    db.add(job)
    db.flush()

    connector = FixtureConnector()
    fetched = connector.fetch(limit=300)
    with SCAN_WRITE_LOCK:
        acquire_database_scan_write_lock_with_retry(db)
        result = process_fetched_items(db, fetched, scan_id=job.id)

        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        job.items_found = result.raw_items_loaded
        job.items_saved = result.normalized_items_created
        job.signals_detected = result.signals_detected
        job.clusters_created = result.clusters_created
        job.opportunities_created = result.opportunities_created
        job.outcome_message = scan_outcome_message(result)
        db.commit()
    return {
        "raw_items_loaded": result.raw_items_loaded,
        "normalized_items_created": result.normalized_items_created,
        "signals_detected": result.signals_detected,
        "clusters_created": result.clusters_created,
        "opportunities_created": result.opportunities_created,
    }


def stats(db: Session) -> dict:
    total_items = (
        db.scalar(select(NormalizedItem).count())
        if False
        else len(db.scalars(select(NormalizedItem.id)).all())
    )
    signals = len(
        db.scalars(select(ItemSignal.id).where(ItemSignal.is_problem_signal.is_(True))).all()
    )
    clusters = len(db.scalars(select(Cluster.id)).all())
    opportunities = len(db.scalars(select(Opportunity.id)).all())
    source_counts = Counter(db.scalars(select(NormalizedItem.source)).all())
    pain_scores = [row for row in db.scalars(select(ItemSignal.pain_score)).all()]
    distribution = [
        {"bucket": "0.0-0.2", "count": sum(0 <= score < 0.2 for score in pain_scores)},
        {"bucket": "0.2-0.4", "count": sum(0.2 <= score < 0.4 for score in pain_scores)},
        {"bucket": "0.4-0.6", "count": sum(0.4 <= score < 0.6 for score in pain_scores)},
        {"bucket": "0.6-0.8", "count": sum(0.6 <= score < 0.8 for score in pain_scores)},
        {"bucket": "0.8-1.0", "count": sum(0.8 <= score <= 1 for score in pain_scores)},
    ]
    return {
        "total_items": total_items,
        "problem_signals": signals,
        "clusters": clusters,
        "opportunities": opportunities,
        "source_breakdown": [
            {"source": key, "count": value} for key, value in source_counts.items()
        ],
        "pain_distribution": distribution,
    }
