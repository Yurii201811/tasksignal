import math
from uuid import UUID

import pytest

from app.services.opportunity_threads.service import (
    CandidateFingerprint,
    SnapshotFingerprint,
    choose_thread_match,
    content_hash,
    evidence_hash,
    normalized_title_tokens,
)


def fingerprint(
    *,
    evidence: set[str],
    title: str = "CI workflow pain",
    vector: list[float] | None = None,
    model: str | None = "model-a",
    backend: str | None = "backend-a",
) -> SnapshotFingerprint:
    return SnapshotFingerprint(
        evidence_hash=evidence_hash(evidence),
        content_hash="c" * 64,
        evidence_text_hashes=frozenset(evidence),
        title_tokens=normalized_title_tokens(title),
        centroid=tuple(vector or [1.0, 0.0]),
        embedding_model=model,
        embedding_backend=backend,
    )


def candidate(
    value: int,
    **kwargs,
) -> CandidateFingerprint:
    return CandidateFingerprint(
        thread_id=UUID(int=value),
        snapshot_id=UUID(int=value + 100),
        fingerprint=fingerprint(**kwargs),
    )


def test_fingerprint_hashes_are_deterministic_and_exclude_decision_fields() -> None:
    first_evidence = evidence_hash({"b", "a"})
    second_evidence = evidence_hash({"a", "b"})
    base = {
        "title": "Build helper",
        "problem_statement": "Manual work",
        "evidence_hash": first_evidence,
    }

    assert first_evidence == second_evidence
    assert len(first_evidence) == 64
    assert content_hash(base) == content_hash(
        {**base, "review_state": "rejected", "review_note": "local"}
    )
    assert normalized_title_tokens("  Café CI—PAIN  ") == frozenset(
        {"café", "ci", "pain"}
    )


def test_unique_exact_evidence_match_wins_immediately() -> None:
    current = fingerprint(evidence={"a", "b"}, vector=[0.0, 1.0])
    exact = candidate(1, evidence={"a", "b"}, vector=[1.0, 0.0], model="other")
    unrelated = candidate(2, evidence={"z"})

    decision = choose_thread_match(current, [unrelated, exact])

    assert decision.thread_id == exact.thread_id
    assert decision.method == "exact_evidence"
    assert decision.confidence == 1.0


def test_multiple_exact_candidates_are_conservatively_ambiguous() -> None:
    current = fingerprint(evidence={"same"})

    decision = choose_thread_match(
        current,
        [candidate(2, evidence={"same"}), candidate(1, evidence={"same"})],
    )

    assert decision.thread_id is None
    assert decision.method == "new_ambiguous"
    assert decision.confidence == 1.0


def test_weighted_match_accepts_threshold_and_exact_margin_boundaries() -> None:
    current = fingerprint(evidence={"a", "b", "c"}, title="alpha beta gamma delta")
    best = candidate(
        2,
        evidence={"a", "b", "d", "e"},
        title="alpha beta gamma delta epsilon",
    )
    runner_cosine = 11 / 12
    runner_up = candidate(
        1,
        evidence={"a", "b", "d", "e"},
        title="alpha beta gamma delta epsilon",
        vector=[runner_cosine, math.sqrt(1 - runner_cosine**2)],
    )

    decision = choose_thread_match(current, [runner_up, best])

    assert decision.thread_id == best.thread_id
    assert decision.method == "weighted_similarity"
    assert decision.confidence == pytest.approx(0.82)
    assert decision.margin == pytest.approx(0.05)


def test_weighted_match_rejects_below_threshold_or_ambiguous_lead() -> None:
    current = fingerprint(evidence={"a", "b"}, title="alpha beta")
    low = candidate(
        1,
        evidence={"x", "y"},
        title="other title",
        vector=[0.8, 0.6],
    )
    tied_a = candidate(2, evidence={"a", "x"}, title="alpha beta")
    tied_b = candidate(3, evidence={"a", "y"}, title="alpha beta")

    below = choose_thread_match(current, [low])
    ambiguous = choose_thread_match(current, [tied_b, tied_a])

    assert below.thread_id is None
    assert below.method == "new_below_threshold"
    assert ambiguous.thread_id is None
    assert ambiguous.method == "new_ambiguous"
    assert ambiguous.best_candidate_thread_id == tied_a.thread_id


def test_weighted_match_never_compares_cross_model_or_dimension_vectors() -> None:
    current = fingerprint(evidence={"a"})
    other_model = candidate(1, evidence={"a", "b"}, model="model-b")
    other_backend = candidate(2, evidence={"a", "c"}, backend="backend-b")
    other_width = candidate(3, evidence={"a", "d"}, vector=[1.0, 0.0, 0.0])

    decision = choose_thread_match(current, [other_model, other_backend, other_width])

    assert decision.thread_id is None
    assert decision.method == "new_below_threshold"
    assert decision.confidence is None
