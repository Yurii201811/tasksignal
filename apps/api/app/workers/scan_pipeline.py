from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    Cluster,
    ClusterItem,
    ItemEmbedding,
    ItemSignal,
    NormalizedItem,
    Opportunity,
    RawItem,
    ScanJob,
    Source,
)
from app.services.clustering.service import cluster_items
from app.services.detection.rules import detect_problem_signal
from app.services.embeddings.service import EmbeddingService, cosine_similarity
from app.services.generation.service import generate_opportunity
from app.services.ingestion.connectors import (
    BaseConnector,
    FixtureConnector,
    GitHubIssuesConnector,
    HackerNewsConnector,
    RedditConnector,
    StackExchangeConnector,
    connector_display_name,
    without_raw_author,
)
from app.services.ingestion.normalization import normalize
from app.services.ingestion.types import RawFetchedItem
from app.services.scoring.service import score_opportunity

ConnectorFactory = Callable[[], BaseConnector]

SOURCE_ALIASES = {
    "fixture": "fixture",
    "fixtures": "fixture",
    "github": "github",
    "github_issues": "github",
    "github-issues": "github",
    "hacker-news": "hackernews",
    "hackernews": "hackernews",
    "hn": "hackernews",
    "reddit": "reddit",
    "stack-exchange": "stackexchange",
    "stack_exchange": "stackexchange",
    "stackexchange": "stackexchange",
    "stackoverflow": "stackexchange",
}

CONNECTOR_FACTORIES: dict[str, ConnectorFactory] = {
    "fixture": FixtureConnector,
    "github": GitHubIssuesConnector,
    "hackernews": HackerNewsConnector,
    "reddit": RedditConnector,
    "stackexchange": StackExchangeConnector,
}


@dataclass(frozen=True)
class ScanPipelineResult:
    raw_items_loaded: int
    normalized_items_created: int
    signals_detected: int
    clusters_created: int
    opportunities_created: int


def canonical_source(source: str) -> str:
    normalized = source.strip().lower().replace(" ", "-")
    return SOURCE_ALIASES.get(normalized, normalized)


def connector_for_source(source: str) -> BaseConnector:
    source_type = canonical_source(source)
    factory = CONNECTOR_FACTORIES.get(source_type)
    if factory is None:
        supported = ", ".join(sorted(CONNECTOR_FACTORIES))
        raise ValueError(f"Unsupported source '{source}'. Supported sources: {supported}.")
    return factory()


def ensure_source(db: Session, source_type: str) -> Source:
    source = db.scalar(select(Source).where(Source.type == source_type))
    if source is not None:
        return source

    source = Source(
        name=connector_display_name(source_type),
        type=source_type,
        config_json={},
        enabled=source_type != "fixture",
    )
    db.add(source)
    db.flush()
    return source


def save_fetched_items(db: Session, fetched: list[RawFetchedItem]) -> list[UUID]:
    created_item_ids: list[UUID] = []
    for raw in fetched:
        raw_exists = db.scalar(
            select(RawItem.id).where(
                RawItem.source == raw.source,
                RawItem.external_id == raw.external_id,
            )
        )
        if raw_exists is None:
            db.add(
                RawItem(
                    source=raw.source,
                    external_id=raw.external_id,
                    raw_json=without_raw_author(raw.source, raw.raw_json),
                    fetched_at=raw.fetched_at,
                )
            )

        normalized = normalize(raw)
        if not normalized["title"] and not normalized["body"]:
            continue
        exists = db.scalar(
            select(NormalizedItem.id).where(
                NormalizedItem.text_hash == normalized["text_hash"]
            )
        )
        if exists is not None:
            continue

        item = NormalizedItem(**normalized)
        db.add(item)
        db.flush()
        created_item_ids.append(item.id)
    return created_item_ids


def detect_signals(db: Session, item_ids: list[UUID]) -> int:
    if not item_ids:
        return 0

    items = db.scalars(select(NormalizedItem).where(NormalizedItem.id.in_(item_ids))).all()
    signals_detected = 0
    for item in items:
        existing = db.scalar(select(ItemSignal.id).where(ItemSignal.item_id == item.id))
        if existing is not None:
            continue

        result = detect_problem_signal(item.title, item.body)
        if result.is_problem_signal:
            signals_detected += 1
        db.add(
            ItemSignal(
                item_id=item.id,
                is_problem_signal=result.is_problem_signal,
                signal_type=result.signal_type,
                pain_score=result.pain_score,
                task_concreteness_score=result.task_concreteness_score,
                buying_intent_score=result.buying_intent_score,
                evidence_spans_json=result.evidence_spans,
                classifier_version="rules-v1",
            )
        )
    db.flush()
    return signals_detected


def embed_signals(
    db: Session,
    signal_rows: list[tuple[NormalizedItem, ItemSignal]],
) -> dict[UUID, list[float]]:
    embedder = EmbeddingService()
    texts = [f"{item.title}. {item.body}" for item, _signal in signal_rows]
    vectors = embedder.embed_texts(texts)
    embeddings_by_item: dict[UUID, list[float]] = {}
    for (item, _signal), vector in zip(signal_rows, vectors, strict=True):
        embeddings_by_item[item.id] = vector
        existing = db.scalar(select(ItemEmbedding.id).where(ItemEmbedding.item_id == item.id))
        if existing is None:
            db.add(
                ItemEmbedding(
                    item_id=item.id,
                    embedding=vector,
                    model_name=f"{embedder.model_name}:{embedder.backend}",
                )
            )
    db.flush()
    return embeddings_by_item


def generate_clusters_and_opportunities(
    db: Session,
    signal_rows: list[tuple[NormalizedItem, ItemSignal]],
    embeddings_by_item: dict[UUID, list[float]],
) -> tuple[int, int]:
    cluster_inputs = [
        {
            "id": item.id,
            "source": item.source,
            "url": item.url,
            "title": item.title,
            "body": item.body,
            "created_at": item.created_at,
            "signal_type": signal.signal_type,
            "pain_score": signal.pain_score,
            "task_concreteness_score": signal.task_concreteness_score,
            "buying_intent_score": signal.buying_intent_score,
            "evidence_spans": signal.evidence_spans_json,
        }
        for item, signal in signal_rows
    ]
    candidates = cluster_items(cluster_inputs, embeddings_by_item)
    item_lookup = {entry["id"]: entry for entry in cluster_inputs}
    clusters_created = 0
    opportunities_created = 0

    for candidate in candidates:
        cluster = Cluster(
            title=candidate.title,
            summary=candidate.summary,
            centroid_embedding=candidate.centroid,
            size=len(candidate.item_ids),
        )
        db.add(cluster)
        db.flush()
        clusters_created += 1

        group_items = [item_lookup[item_id] for item_id in candidate.item_ids]
        for item_id in candidate.item_ids:
            db.add(
                ClusterItem(
                    cluster_id=cluster.id,
                    item_id=item_id,
                    similarity_score=cosine_similarity(
                        candidate.centroid, embeddings_by_item[item_id]
                    ),
                )
            )

        score = score_opportunity(group_items, f"{candidate.title} {candidate.summary}")
        generated = generate_opportunity(candidate.title, candidate.summary, group_items, score)
        db.add(
            Opportunity(
                cluster_id=cluster.id,
                title=generated["title"],
                problem_statement=generated["problem_statement"],
                target_user=generated["target_user"],
                current_workaround=generated["current_workaround"],
                suggested_mvp=generated["suggested_mvp"],
                why_now=generated["why_now"],
                feasibility_score=generated["feasibility_score"],
                opportunity_score=generated["opportunity_score"],
                competition_notes=generated["competition_notes"],
                scoring_breakdown_json={**score, "common_phrases": generated["common_phrases"]},
                generated_prompt=generated["generated_prompt"],
            )
        )
        opportunities_created += 1

    db.flush()
    return clusters_created, opportunities_created


def process_fetched_items(
    db: Session,
    fetched: list[RawFetchedItem],
) -> ScanPipelineResult:
    created_item_ids = save_fetched_items(db, fetched)
    signals_detected = detect_signals(db, created_item_ids)

    if not created_item_ids:
        return ScanPipelineResult(
            raw_items_loaded=len(fetched),
            normalized_items_created=0,
            signals_detected=0,
            clusters_created=0,
            opportunities_created=0,
        )

    signal_rows = db.execute(
        select(NormalizedItem, ItemSignal)
        .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id)
        .where(
            NormalizedItem.id.in_(created_item_ids),
            ItemSignal.is_problem_signal.is_(True),
        )
    ).all()
    if not signal_rows:
        return ScanPipelineResult(
            raw_items_loaded=len(fetched),
            normalized_items_created=len(created_item_ids),
            signals_detected=signals_detected,
            clusters_created=0,
            opportunities_created=0,
        )

    embeddings_by_item = embed_signals(db, signal_rows)
    clusters_created, opportunities_created = generate_clusters_and_opportunities(
        db,
        signal_rows,
        embeddings_by_item,
    )
    return ScanPipelineResult(
        raw_items_loaded=len(fetched),
        normalized_items_created=len(created_item_ids),
        signals_detected=signals_detected,
        clusters_created=clusters_created,
        opportunities_created=opportunities_created,
    )


def run_scan_pipeline(
    db: Session,
    connector: BaseConnector,
    query: str,
    limit: int,
) -> ScanPipelineResult:
    fetched = connector.fetch(query=query, limit=limit)
    return process_fetched_items(db, fetched)


def process_scan(
    db: Session,
    source: str,
    query: str = "",
    limit: int = 30,
    connector: BaseConnector | None = None,
) -> ScanJob:
    source_type = canonical_source(source)
    if connector is None:
        connector = connector_for_source(source_type)

    source_record = ensure_source(db, source_type)
    job = ScanJob(
        source_id=source_record.id,
        status="queued",
        query=query,
        items_found=0,
        items_saved=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.commit()

        result = run_scan_pipeline(
            db,
            connector=connector,
            query=query,
            limit=max(1, min(limit, 100)),
        )
        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        job.items_found = result.raw_items_loaded
        job.items_saved = result.normalized_items_created
        job.error_message = None
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        db.rollback()
        failed_job = db.get(ScanJob, job.id)
        if failed_job is None:
            raise
        failed_job.status = "failed"
        failed_job.finished_at = datetime.now(UTC)
        failed_job.error_message = str(exc)
        db.commit()
        db.refresh(failed_job)
        return failed_job
