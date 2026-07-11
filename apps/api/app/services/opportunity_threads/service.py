from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.all_models import (
    Cluster,
    ClusterItem,
    NormalizedItem,
    Opportunity,
    OpportunityDecisionEvent,
    OpportunityThread,
    ResearchProjectRun,
    now_utc,
)

CONTENT_HASH_FIELDS = (
    "competition_notes",
    "current_workaround",
    "evidence_hash",
    "feasibility_score",
    "generated_prompt",
    "opportunity_score",
    "problem_statement",
    "scoring_breakdown",
    "suggested_mvp",
    "target_user",
    "title",
    "why_now",
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def namespaced_hash(namespace: bytes, value: Any) -> str:
    return hashlib.sha256(namespace + b"\0" + canonical_json(value)).hexdigest()


def evidence_hash(text_hashes: set[str] | frozenset[str]) -> str:
    return namespaced_hash(b"tasksignal:evidence-set:v1", sorted(set(text_hashes)))


def content_hash(values: dict[str, Any]) -> str:
    canonical_values = {key: values.get(key) for key in CONTENT_HASH_FIELDS if key in values}
    return namespaced_hash(b"tasksignal:opportunity-content:v1", canonical_values)


def normalized_title_tokens(title: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    return frozenset(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def compatible_cosine(
    left: tuple[float, ...] | None,
    right: tuple[float, ...] | None,
) -> float | None:
    if not left or not right or len(left) != len(right):
        return None
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, numerator / (left_norm * right_norm)))


@dataclass(frozen=True)
class SnapshotFingerprint:
    evidence_hash: str
    content_hash: str
    evidence_text_hashes: frozenset[str]
    title_tokens: frozenset[str]
    centroid: tuple[float, ...] | None
    embedding_model: str | None
    embedding_backend: str | None


@dataclass(frozen=True)
class CandidateFingerprint:
    thread_id: UUID
    snapshot_id: UUID
    fingerprint: SnapshotFingerprint


@dataclass(frozen=True)
class CandidateScore:
    thread_id: UUID
    snapshot_id: UUID
    score: float
    centroid_similarity: float
    evidence_jaccard: float
    title_jaccard: float


@dataclass(frozen=True)
class MatchDecision:
    thread_id: UUID | None
    method: str
    confidence: float | None = None
    margin: float | None = None
    centroid_similarity: float | None = None
    evidence_jaccard: float | None = None
    title_jaccard: float | None = None
    best_candidate_thread_id: UUID | None = None


class ThreadVersionConflict(ValueError):
    pass


class DetachNotAllowed(ValueError):
    pass


def lock_thread_version(
    db: Session,
    *,
    thread: OpportunityThread,
    expected_version: int | None,
) -> int:
    """Atomically validate a thread version and hold its row until commit."""
    expected = thread.version if expected_version is None else expected_version
    result = db.execute(
        update(OpportunityThread)
        .where(
            OpportunityThread.id == thread.id,
            OpportunityThread.version == expected,
        )
        .values(version=expected)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        current = db.scalar(
            select(OpportunityThread.version).where(OpportunityThread.id == thread.id)
        )
        current_label = "missing" if current is None else str(current)
        raise ThreadVersionConflict(
            f"Thread version conflict: expected {expected}, current {current_label}."
        )
    db.refresh(thread)
    return expected


def score_candidate(
    current: SnapshotFingerprint,
    candidate: CandidateFingerprint,
) -> CandidateScore | None:
    other = candidate.fingerprint
    if (
        current.embedding_model is None
        or current.embedding_backend is None
        or current.embedding_model != other.embedding_model
        or current.embedding_backend != other.embedding_backend
    ):
        return None
    centroid = compatible_cosine(current.centroid, other.centroid)
    if centroid is None:
        return None
    evidence = jaccard(current.evidence_text_hashes, other.evidence_text_hashes)
    title = jaccard(current.title_tokens, other.title_tokens)
    score = 0.60 * centroid + 0.25 * evidence + 0.15 * title
    return CandidateScore(
        thread_id=candidate.thread_id,
        snapshot_id=candidate.snapshot_id,
        score=score,
        centroid_similarity=centroid,
        evidence_jaccard=evidence,
        title_jaccard=title,
    )


def choose_thread_match(
    current: SnapshotFingerprint,
    candidates: list[CandidateFingerprint],
) -> MatchDecision:
    exact = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.fingerprint.evidence_hash == current.evidence_hash
        ),
        key=lambda candidate: str(candidate.thread_id),
    )
    if len(exact) == 1:
        return MatchDecision(
            thread_id=exact[0].thread_id,
            method="exact_evidence",
            confidence=1.0,
            best_candidate_thread_id=exact[0].thread_id,
        )
    if len(exact) > 1:
        return MatchDecision(
            thread_id=None,
            method="new_ambiguous",
            confidence=1.0,
            margin=0.0,
            best_candidate_thread_id=exact[0].thread_id,
        )
    if not candidates:
        return MatchDecision(thread_id=None, method="new_no_candidates")

    scored = [score for candidate in candidates if (score := score_candidate(current, candidate))]
    scored.sort(key=lambda score: (-score.score, str(score.thread_id)))
    if not scored:
        return MatchDecision(thread_id=None, method="new_below_threshold")

    best = scored[0]
    margin = best.score - scored[1].score if len(scored) > 1 else None
    common = {
        "confidence": best.score,
        "margin": margin,
        "centroid_similarity": best.centroid_similarity,
        "evidence_jaccard": best.evidence_jaccard,
        "title_jaccard": best.title_jaccard,
        "best_candidate_thread_id": best.thread_id,
    }
    if best.score >= 0.82 and (margin is None or margin >= 0.05):
        return MatchDecision(
            thread_id=best.thread_id,
            method="weighted_similarity",
            **common,
        )
    method = "new_ambiguous" if best.score >= 0.82 else "new_below_threshold"
    return MatchDecision(thread_id=None, method=method, **common)


def cluster_evidence_hashes(db: Session, cluster_id: UUID) -> frozenset[str]:
    return frozenset(
        db.scalars(
            select(NormalizedItem.text_hash)
            .join(ClusterItem, ClusterItem.item_id == NormalizedItem.id)
            .where(ClusterItem.cluster_id == cluster_id)
        ).all()
    )


def fingerprint_for_snapshot(
    db: Session,
    snapshot: Opportunity,
) -> SnapshotFingerprint:
    cluster = db.get(Cluster, snapshot.cluster_id)
    centroid = (
        tuple(float(value) for value in cluster.centroid_embedding)
        if cluster is not None and cluster.centroid_embedding
        else None
    )
    return SnapshotFingerprint(
        evidence_hash=snapshot.evidence_hash,
        content_hash=snapshot.content_hash,
        evidence_text_hashes=cluster_evidence_hashes(db, snapshot.cluster_id),
        title_tokens=normalized_title_tokens(snapshot.title),
        centroid=centroid,
        embedding_model=snapshot.embedding_model,
        embedding_backend=snapshot.embedding_backend,
    )


def candidate_fingerprints(
    db: Session,
    *,
    project_id: UUID,
    scan_id: UUID | None,
    current_evidence_hash: str,
) -> list[CandidateFingerprint]:
    excluded_threads = set(
        db.scalars(
            select(OpportunityDecisionEvent.thread_id)
            .join(
                Opportunity,
                Opportunity.id == OpportunityDecisionEvent.snapshot_id,
            )
            .where(
                OpportunityDecisionEvent.event_type == "snapshot_detached",
                Opportunity.evidence_hash == current_evidence_hash,
            )
        ).all()
    )
    threads = db.scalars(
        select(OpportunityThread)
        .where(
            OpportunityThread.project_id == project_id,
            OpportunityThread.current_snapshot_id.is_not(None),
        )
        .order_by(OpportunityThread.id)
    ).all()
    candidates: list[CandidateFingerprint] = []
    for thread in threads:
        if thread.id in excluded_threads or thread.current_snapshot_id is None:
            continue
        snapshot = db.get(Opportunity, thread.current_snapshot_id)
        if snapshot is None or (scan_id is not None and snapshot.scan_id == scan_id):
            continue
        candidates.append(
            CandidateFingerprint(
                thread_id=thread.id,
                snapshot_id=snapshot.id,
                fingerprint=fingerprint_for_snapshot(db, snapshot),
            )
        )
    return candidates


def generated_content_hash(values: dict[str, Any], snapshot_evidence_hash: str) -> str:
    return content_hash(
        {
            "competition_notes": values["competition_notes"],
            "current_workaround": values["current_workaround"],
            "evidence_hash": snapshot_evidence_hash,
            "feasibility_score": values["feasibility_score"],
            "generated_prompt": values["generated_prompt"],
            "opportunity_score": values["opportunity_score"],
            "problem_statement": values["problem_statement"],
            "scoring_breakdown": values["scoring_breakdown_json"],
            "suggested_mvp": values["suggested_mvp"],
            "target_user": values["target_user"],
            "title": values["title"],
            "why_now": values["why_now"],
        }
    )


def attach_generated_snapshot(
    db: Session,
    *,
    cluster: Cluster,
    scan_id: UUID | None,
    opportunity_values: dict[str, Any],
    embedding_model: str,
    embedding_backend: str,
) -> Opportunity:
    research_run = (
        db.scalar(select(ResearchProjectRun).where(ResearchProjectRun.scan_id == scan_id))
        if scan_id is not None
        else None
    )
    project_id = research_run.project_id if research_run is not None else None
    lineage_status = "complete" if project_id is not None else "untracked"
    evidence_text_hashes = cluster_evidence_hashes(db, cluster.id)
    snapshot_evidence_hash = evidence_hash(evidence_text_hashes)
    snapshot_content_hash = generated_content_hash(
        opportunity_values,
        snapshot_evidence_hash,
    )
    fingerprint = SnapshotFingerprint(
        evidence_hash=snapshot_evidence_hash,
        content_hash=snapshot_content_hash,
        evidence_text_hashes=evidence_text_hashes,
        title_tokens=normalized_title_tokens(opportunity_values["title"]),
        centroid=tuple(float(value) for value in cluster.centroid_embedding or []),
        embedding_model=embedding_model,
        embedding_backend=embedding_backend,
    )

    if project_id is None:
        decision = MatchDecision(thread_id=None, method="new_untracked")
    else:
        decision = choose_thread_match(
            fingerprint,
            candidate_fingerprints(
                db,
                project_id=project_id,
                scan_id=scan_id,
                current_evidence_hash=snapshot_evidence_hash,
            ),
        )
    thread = db.get(OpportunityThread, decision.thread_id) if decision.thread_id else None
    if thread is None:
        thread = OpportunityThread(
            project_id=project_id,
            current_snapshot_id=None,
            lineage_status=lineage_status,
            review_state="new",
            review_note=None,
            decision_updated_at=None,
            version=1,
        )
        db.add(thread)
        db.flush()

    snapshot = Opportunity(
        thread_id=thread.id,
        run_id=research_run.id if research_run is not None else None,
        scan_id=scan_id,
        cluster_id=cluster.id,
        evidence_hash=snapshot_evidence_hash,
        content_hash=snapshot_content_hash,
        match_method=decision.method,
        match_confidence=decision.confidence,
        match_margin=decision.margin,
        centroid_similarity=decision.centroid_similarity,
        evidence_jaccard=decision.evidence_jaccard,
        title_jaccard=decision.title_jaccard,
        embedding_model=embedding_model,
        embedding_backend=embedding_backend,
        review_state=thread.review_state,
        review_note=thread.review_note,
        decision_updated_at=thread.decision_updated_at,
        **opportunity_values,
    )
    db.add(snapshot)
    db.flush()
    thread.current_snapshot_id = snapshot.id
    thread.updated_at = now_utc()
    return snapshot


def set_thread_decision(
    db: Session,
    *,
    thread: OpportunityThread,
    review_state: str,
    review_note: str | None,
    expected_version: int | None,
    actor_type: str = "human",
    agent_session_id: UUID | None = None,
) -> OpportunityThread:
    if (actor_type == "agent") != (agent_session_id is not None):
        raise ValueError("Agent decisions require session provenance; human decisions must omit it.")
    version_before = lock_thread_version(
        db,
        thread=thread,
        expected_version=expected_version,
    )
    normalized_note = review_note.strip() if review_note else None
    if thread.review_state == review_state and thread.review_note == normalized_note:
        return thread

    now = now_utc()
    event = OpportunityDecisionEvent(
        thread_id=thread.id,
        event_type="decision_changed",
        actor_type=actor_type,
        agent_session_id=agent_session_id,
        snapshot_id=thread.current_snapshot_id,
        related_thread_id=None,
        previous_state=thread.review_state,
        next_state=review_state,
        previous_note=thread.review_note,
        next_note=normalized_note,
        details_json={"version_before": version_before},
        created_at=now,
    )
    db.add(event)
    thread.review_state = review_state
    thread.review_note = normalized_note
    thread.decision_updated_at = now
    thread.updated_at = now
    thread.version = version_before + 1
    db.execute(
        update(Opportunity)
        .where(Opportunity.thread_id == thread.id)
        .values(
            review_state=review_state,
            review_note=normalized_note,
            decision_updated_at=now,
        )
    )
    return thread


def clone_snapshot(
    db: Session,
    *,
    source: Opportunity,
    method: str,
    overrides: dict[str, Any],
) -> Opportunity:
    thread = db.get(OpportunityThread, source.thread_id)
    if thread is None:
        raise ValueError("Opportunity thread not found")
    values = {
        "title": source.title,
        "problem_statement": source.problem_statement,
        "target_user": source.target_user,
        "current_workaround": source.current_workaround,
        "suggested_mvp": source.suggested_mvp,
        "why_now": source.why_now,
        "feasibility_score": source.feasibility_score,
        "opportunity_score": source.opportunity_score,
        "competition_notes": source.competition_notes,
        "scoring_breakdown_json": source.scoring_breakdown_json,
        "generated_prompt": source.generated_prompt,
    }
    values.update(overrides)
    snapshot = Opportunity(
        thread_id=thread.id,
        run_id=None,
        scan_id=None,
        cluster_id=source.cluster_id,
        evidence_hash=source.evidence_hash,
        content_hash=generated_content_hash(values, source.evidence_hash),
        match_method=method,
        match_confidence=1.0,
        match_margin=None,
        centroid_similarity=None,
        evidence_jaccard=None,
        title_jaccard=None,
        embedding_model=source.embedding_model,
        embedding_backend=source.embedding_backend,
        review_state=thread.review_state,
        review_note=thread.review_note,
        decision_updated_at=thread.decision_updated_at,
        **values,
    )
    db.add(snapshot)
    db.flush()
    thread.current_snapshot_id = snapshot.id
    thread.updated_at = now_utc()
    return snapshot


def detach_snapshot(
    db: Session,
    *,
    thread: OpportunityThread,
    snapshot: Opportunity,
    expected_version: int,
) -> OpportunityThread:
    if snapshot.thread_id != thread.id:
        raise DetachNotAllowed("Snapshot does not belong to this thread.")
    version_before = lock_thread_version(
        db,
        thread=thread,
        expected_version=expected_version,
    )
    if snapshot.match_method not in {"exact_evidence", "weighted_similarity"}:
        raise DetachNotAllowed("Only automatically matched snapshots can be detached.")
    existing_snapshots = list(
        db.scalars(
            select(Opportunity)
            .where(Opportunity.thread_id == thread.id)
            .order_by(Opportunity.created_at.desc(), Opportunity.id.desc())
        ).all()
    )
    if len(existing_snapshots) < 2:
        raise DetachNotAllowed("A thread must retain at least one snapshot after detach.")

    now = now_utc()
    new_thread = OpportunityThread(
        project_id=thread.project_id,
        current_snapshot_id=None,
        lineage_status=thread.lineage_status,
        review_state="new",
        review_note=None,
        decision_updated_at=None,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(new_thread)
    db.flush()

    remaining = [candidate for candidate in existing_snapshots if candidate.id != snapshot.id]
    if thread.current_snapshot_id == snapshot.id:
        thread.current_snapshot_id = remaining[0].id
        db.flush()

    original_match = {
        "reason": "human_match_correction",
        "original_thread_id": str(thread.id),
        "original_match_method": snapshot.match_method,
        "original_match_confidence": snapshot.match_confidence,
        "original_match_margin": snapshot.match_margin,
        "original_centroid_similarity": snapshot.centroid_similarity,
        "original_evidence_jaccard": snapshot.evidence_jaccard,
        "original_title_jaccard": snapshot.title_jaccard,
    }
    snapshot.thread_id = new_thread.id
    snapshot.review_state = "new"
    snapshot.review_note = None
    snapshot.decision_updated_at = None
    new_thread.current_snapshot_id = snapshot.id
    thread.updated_at = now
    thread.version = version_before + 1

    db.add_all(
        [
            OpportunityDecisionEvent(
                thread_id=thread.id,
                event_type="snapshot_detached",
                actor_type="human",
                snapshot_id=snapshot.id,
                related_thread_id=new_thread.id,
                previous_state=thread.review_state,
                next_state=thread.review_state,
                previous_note=thread.review_note,
                next_note=thread.review_note,
                details_json=original_match,
                created_at=now,
            ),
            OpportunityDecisionEvent(
                thread_id=new_thread.id,
                event_type="thread_created_by_detach",
                actor_type="human",
                snapshot_id=snapshot.id,
                related_thread_id=thread.id,
                previous_state=None,
                next_state="new",
                previous_note=None,
                next_note=None,
                details_json=original_match,
                created_at=now,
            ),
        ]
    )
    return new_thread
