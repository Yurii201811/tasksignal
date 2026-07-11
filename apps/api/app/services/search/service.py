from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    ClusterItem,
    ItemEmbedding,
    ItemSignal,
    NormalizedItem,
    Opportunity,
    OpportunityThread,
    ResearchProjectRun,
    ScanItem,
)
from app.schemas.api import (
    EvidenceSearchHitOut,
    EvidenceSearchObservationOut,
    EvidenceSearchProvenanceOut,
    OpportunityThreadHitOut,
    OpportunityThreadSearchProvenanceOut,
    SemanticSearchOut,
    SemanticSearchRequest,
)
from app.services.embeddings.service import EmbeddingService, cosine_similarity
from app.services.evidence_review.service import (
    calculate_evidence_readiness,
    get_review_snapshots,
)
from app.services.evidence_review.types import EvidenceReviewSnapshot, ReviewState
from app.services.ingestion.normalization import safe_source_url


class SemanticEmbedder(Protocol):
    model_name: str
    backend: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class EvidenceObservation:
    source: str
    source_url: str
    scan_id: UUID
    run_id: UUID | None
    project_id: UUID | None
    run_sequence: int | None


def _sorted_uuids(values: Iterable[UUID]) -> list[UUID]:
    return sorted(set(values), key=str)


def _safe_text(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _safe_excerpt(item: NormalizedItem, signal: ItemSignal | None) -> str:
    spans = signal.evidence_spans_json if signal is not None else []
    candidate = next((span for span in spans if isinstance(span, str) and span.strip()), None)
    return _safe_text(candidate or item.body or item.title, 240)


def _clamped_similarity(left: list[float], right: list[float]) -> float | None:
    if not left or not right or len(left) != len(right):
        return None
    return round(max(0.0, min(1.0, cosine_similarity(left, right))), 6)


def semantic_search(
    db: Session,
    request: SemanticSearchRequest,
    *,
    embedder: SemanticEmbedder | None = None,
) -> SemanticSearchOut:
    active_embedder = embedder or EmbeddingService()
    query_vector = active_embedder.embed_texts([request.query])[0]
    embedding_identity = f"{active_embedder.model_name}:{active_embedder.backend}"

    rows = db.execute(
        select(NormalizedItem, ItemEmbedding, ItemSignal)
        .join(ItemEmbedding, ItemEmbedding.item_id == NormalizedItem.id)
        .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id, isouter=True)
        .where(ItemEmbedding.model_name == embedding_identity)
        .order_by(
            NormalizedItem.id,
            ItemEmbedding.created_at.desc(),
            ItemEmbedding.id.desc(),
        )
    ).all()
    evidence_rows: dict[UUID, tuple[NormalizedItem, ItemEmbedding, ItemSignal | None]] = {}
    for item, embedding, signal in rows:
        evidence_rows.setdefault(item.id, (item, embedding, signal))
    item_ids = set(evidence_rows)

    provenance_rows = (
        db.execute(
            select(
                ScanItem.item_id,
                ScanItem.scan_id,
                ResearchProjectRun.id,
                ResearchProjectRun.project_id,
                ResearchProjectRun.sequence,
                ScanItem.observed_source,
                ScanItem.observed_url,
            )
            .select_from(ScanItem)
            .join(
                ResearchProjectRun,
                ResearchProjectRun.scan_id == ScanItem.scan_id,
                isouter=True,
            )
            .where(ScanItem.item_id.in_(item_ids))
        ).all()
        if item_ids
        else []
    )
    scan_ids_by_item: dict[UUID, set[UUID]] = defaultdict(set)
    run_ids_by_item: dict[UUID, set[UUID]] = defaultdict(set)
    project_ids_by_item: dict[UUID, set[UUID]] = defaultdict(set)
    observations_by_item: dict[UUID, list[EvidenceObservation]] = defaultdict(list)
    for (
        item_id,
        scan_id,
        run_id,
        project_id,
        run_sequence,
        observed_source,
        observed_url,
    ) in provenance_rows:
        scan_ids_by_item[item_id].add(scan_id)
        if run_id is not None:
            run_ids_by_item[item_id].add(run_id)
        if project_id is not None:
            project_ids_by_item[item_id].add(project_id)
        item = evidence_rows[item_id][0]
        observations_by_item[item_id].append(
            EvidenceObservation(
                source=observed_source or item.source,
                source_url=safe_source_url(
                    observed_url or item.url,
                    fallback="",
                ),
                scan_id=scan_id,
                run_id=run_id,
                project_id=project_id,
                run_sequence=run_sequence,
            )
        )

    memberships: dict[UUID, list[tuple[UUID, UUID | None, str]]] = defaultdict(list)
    if item_ids:
        for item_id, thread_id, project_id, review_state in db.execute(
            select(
                ClusterItem.item_id,
                OpportunityThread.id,
                OpportunityThread.project_id,
                OpportunityThread.review_state,
            )
            .select_from(ClusterItem)
            .join(Opportunity, Opportunity.cluster_id == ClusterItem.cluster_id)
            .join(
                OpportunityThread,
                OpportunityThread.current_snapshot_id == Opportunity.id,
            )
            .where(ClusterItem.item_id.in_(item_ids))
        ).all():
            memberships[item_id].append((thread_id, project_id, review_state))

    review_snapshots = get_review_snapshots(db, item_ids)
    evidence_hits: list[EvidenceSearchHitOut] = []
    for item_id, (item, embedding, signal) in evidence_rows.items():
        if request.signal_type is not None and (
            signal is None or signal.signal_type.casefold() != request.signal_type.casefold()
        ):
            continue
        if request.project_id is not None and request.project_id not in project_ids_by_item[item_id]:
            continue
        all_observations = observations_by_item[item_id]
        candidate_observations = all_observations
        if request.project_id is not None:
            candidate_observations = [
                observation
                for observation in candidate_observations
                if observation.project_id == request.project_id
            ]
        if request.source is not None:
            candidate_observations = [
                observation
                for observation in candidate_observations
                if observation.source.casefold() == request.source.casefold()
            ]
            if not candidate_observations and (
                all_observations or item.source.casefold() != request.source.casefold()
            ):
                continue
        if request.review_state is not None and not any(
            state == request.review_state.value
            and (request.project_id is None or project_id == request.project_id)
            for _thread_id, project_id, state in memberships[item_id]
        ):
            continue
        score = _clamped_similarity(query_vector, list(embedding.embedding))
        if score is None:
            continue
        review = review_snapshots.get(item_id, EvidenceReviewSnapshot())
        ordered_observations = sorted(
            candidate_observations,
            key=lambda observation: (
                -(observation.run_sequence or 0),
                observation.source,
                observation.source_url,
                str(observation.scan_id),
            ),
        )
        display_observation = ordered_observations[0] if ordered_observations else None
        evidence_hits.append(
            EvidenceSearchHitOut(
                id=item.id,
                source=(display_observation.source if display_observation else item.source),
                title=_safe_text(item.title, 180),
                excerpt=_safe_excerpt(item, signal),
                source_url=(
                    display_observation.source_url
                    if display_observation
                    else safe_source_url(item.url, fallback="")
                ),
                match_score=score,
                signal_type=signal.signal_type if signal is not None else None,
                review_label=review.review_label,
                created_at=item.created_at,
                untrusted_evidence=True,
                provenance=EvidenceSearchProvenanceOut(
                    evidence_hash=item.text_hash,
                    scan_ids=(
                        _sorted_uuids(
                            observation.scan_id for observation in ordered_observations
                        )
                        if ordered_observations
                        else _sorted_uuids(scan_ids_by_item[item_id])
                    ),
                    run_ids=(
                        _sorted_uuids(
                            observation.run_id
                            for observation in ordered_observations
                            if observation.run_id is not None
                        )
                        if ordered_observations
                        else _sorted_uuids(run_ids_by_item[item_id])
                    ),
                    project_ids=(
                        _sorted_uuids(
                            observation.project_id
                            for observation in ordered_observations
                            if observation.project_id is not None
                        )
                        if ordered_observations
                        else _sorted_uuids(project_ids_by_item[item_id])
                    ),
                    observations=[
                        EvidenceSearchObservationOut(
                            source=observation.source,
                            source_url=observation.source_url,
                            scan_id=observation.scan_id,
                            run_id=observation.run_id,
                            project_id=observation.project_id,
                        )
                        for observation in ordered_observations
                    ],
                ),
            )
        )

    evidence_hits.sort(key=lambda hit: (-hit.match_score, str(hit.id)))
    evidence_hits = evidence_hits[: request.limit]
    scores_by_item = {hit.id: hit.match_score for hit in evidence_hits}

    thread_hits: list[OpportunityThreadHitOut] = []
    threads = db.scalars(
        select(OpportunityThread)
        .where(OpportunityThread.current_snapshot_id.is_not(None))
        .order_by(OpportunityThread.id)
    ).all()
    for thread in threads:
        if request.project_id is not None and thread.project_id != request.project_id:
            continue
        if request.review_state is not None and thread.review_state != request.review_state.value:
            continue
        if thread.current_snapshot_id is None:
            continue
        snapshot = db.get(Opportunity, thread.current_snapshot_id)
        if snapshot is None:
            continue
        cluster_item_ids = set(
            db.scalars(
                select(ClusterItem.item_id).where(ClusterItem.cluster_id == snapshot.cluster_id)
            ).all()
        )
        matched_ids = sorted(
            cluster_item_ids & scores_by_item.keys(),
            key=lambda item_id: (-scores_by_item[item_id], str(item_id)),
        )
        if not matched_ids:
            continue

        readiness_items = list(
            db.scalars(select(NormalizedItem).where(NormalizedItem.id.in_(cluster_item_ids))).all()
        )
        readiness_snapshots = get_review_snapshots(
            db,
            [item.id for item in readiness_items],
        )
        thread_hits.append(
            OpportunityThreadHitOut(
                id=thread.id,
                project_id=thread.project_id,
                title=_safe_text(snapshot.title, 180),
                summary=_safe_text(snapshot.problem_statement, 240),
                match_score=max(scores_by_item[item_id] for item_id in matched_ids),
                matched_evidence_ids=matched_ids,
                matched_evidence_count=len(matched_ids),
                review_state=ReviewState(thread.review_state),
                lineage_status=thread.lineage_status,
                evidence_readiness=calculate_evidence_readiness(
                    readiness_items,
                    readiness_snapshots,
                ),
                provenance=OpportunityThreadSearchProvenanceOut(
                    snapshot_id=snapshot.id,
                    run_id=snapshot.run_id,
                    scan_id=snapshot.scan_id,
                    evidence_hash=snapshot.evidence_hash,
                    content_hash=snapshot.content_hash,
                    match_method=snapshot.match_method,
                    match_confidence=snapshot.match_confidence,
                ),
            )
        )

    thread_hits.sort(key=lambda hit: (-hit.match_score, str(hit.id)))
    return SemanticSearchOut(
        evidence_hits=evidence_hits,
        opportunity_threads=thread_hits[: request.limit],
    )
