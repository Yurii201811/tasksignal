from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
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
    ScanJob,
    Source,
)
from app.services.clustering.service import cluster_items
from app.services.detection.rules import detect_problem_signal
from app.services.embeddings.service import EmbeddingService, cosine_similarity
from app.services.generation.service import generate_opportunity
from app.services.ingestion.connectors import FixtureConnector
from app.services.ingestion.normalization import normalize
from app.services.scoring.service import score_opportunity


def reset_demo_data(db: Session) -> None:
    for model in [
        Label,
        Opportunity,
        ClusterItem,
        Cluster,
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


def process_demo(db: Session, reset: bool = True) -> dict[str, int]:
    if reset:
        reset_demo_data(db)
    ensure_sources(db)
    job = ScanJob(status="running", query="fixture demo")
    db.add(job)
    db.flush()

    connector = FixtureConnector()
    fetched = connector.fetch(limit=300)
    normalized_created = 0
    for raw in fetched:
        db.add(
            RawItem(
                source=raw.source,
                external_id=raw.external_id,
                raw_json=raw.raw_json,
                fetched_at=raw.fetched_at,
            )
        )
        normalized = normalize(raw)
        exists = db.scalar(
            select(NormalizedItem).where(NormalizedItem.text_hash == normalized["text_hash"])
        )
        if exists:
            continue
        db.add(NormalizedItem(**normalized))
        normalized_created += 1
    db.flush()

    items = db.scalars(select(NormalizedItem)).all()
    signals_detected = 0
    for item in items:
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

    signal_rows = db.execute(
        select(NormalizedItem, ItemSignal)
        .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id)
        .where(ItemSignal.is_problem_signal.is_(True))
    ).all()
    embedder = EmbeddingService()
    texts = [f"{item.title}. {item.body}" for item, _signal in signal_rows]
    vectors = embedder.embed_texts(texts)
    embeddings_by_item: dict[UUID, list[float]] = {}
    for (item, _signal), vector in zip(signal_rows, vectors, strict=True):
        embeddings_by_item[item.id] = vector
        db.add(
            ItemEmbedding(
                item_id=item.id,
                embedding=vector,
                model_name=f"{embedder.model_name}:{embedder.backend}",
            )
        )
    db.flush()

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

    job.status = "completed"
    job.finished_at = datetime.now(UTC)
    job.items_found = len(fetched)
    job.items_saved = normalized_created
    db.commit()
    return {
        "raw_items_loaded": len(fetched),
        "normalized_items_created": normalized_created,
        "signals_detected": signals_detected,
        "clusters_created": clusters_created,
        "opportunities_created": opportunities_created,
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
