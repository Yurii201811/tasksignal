from __future__ import annotations

from datetime import UTC, datetime

from app.services.generation.service import generate_opportunity
from app.services.scoring.service import score_opportunity


def _sample_items() -> list[dict]:
    return [
        {
            "source": "github",
            "title": "GitHub Actions logs are painful",
            "body": "Every week developers copy paste CI errors into spreadsheets.",
            "created_at": datetime(2026, 5, 1, tzinfo=UTC),
            "signal_type": "manual_workflow",
            "pain_score": 0.8,
            "task_concreteness_score": 0.7,
            "buying_intent_score": 0.2,
            "evidence_spans": ["Every week developers copy paste CI errors."],
            "url": "https://example.test/ci-errors",
        }
        for _ in range(4)
    ]


def test_generated_prompt_includes_evidence_ranking_and_privacy_sections() -> None:
    items = _sample_items()
    score = score_opportunity(items, "GitHub Actions workflow debugging assistant")
    opportunity = generate_opportunity(
        "Developers need clearer GitHub Actions failure diagnosis",
        "4 related signals.",
        items,
        score,
    )
    prompt = opportunity["generated_prompt"]

    assert "Every week developers copy paste CI errors." in prompt
    assert "https://example.test/ci-errors" in prompt
    assert "## Ranking rationale" in prompt
    assert "Frequency" in prompt or "frequency" in prompt
    assert "## Trust and privacy constraints" in prompt
    assert "author hashes or null" in prompt.lower()
    assert "## Evidence focus" in prompt


def test_generated_prompt_omits_raw_author_identity() -> None:
    items = [
        {
            "source": "github",
            "title": "CI bot keeps failing on generated code",
            "body": "AliceExample says the generated code keeps missing tests.",
            "author": "AliceExample",
            "username": "alice_example",
            "raw_author": "AliceExample",
            "author_hash": "abc123hashedauthor",
            "created_at": datetime(2026, 5, 1, tzinfo=UTC),
            "signal_type": "manual_workflow",
            "pain_score": 0.7,
            "task_concreteness_score": 0.8,
            "buying_intent_score": 0.1,
            "evidence_spans": ["Generated code keeps missing tests."],
            "url": "https://example.test/generated-code",
        }
        for _ in range(3)
    ]
    score = score_opportunity(items, "AI-generated code needs production-readiness audits")
    opportunity = generate_opportunity(
        "AI-generated code needs production-readiness audits",
        "3 related public signals.",
        items,
        score,
    )
    prompt = opportunity["generated_prompt"]

    assert "AliceExample" not in prompt
    assert "alice_example" not in prompt
    assert "abc123hashedauthor" not in prompt


def test_generated_prompt_uses_tasksignal_endpoints_not_import_process() -> None:
    items = _sample_items()
    score = score_opportunity(items, "GitHub Actions workflow debugging assistant")
    opportunity = generate_opportunity(
        "Developers need clearer GitHub Actions failure diagnosis",
        "4 related signals.",
        items,
        score,
    )
    prompt = opportunity["generated_prompt"]

    assert "POST /api/process/demo" in prompt
    assert "POST /api/scans" in prompt
    assert "POST /api/import" not in prompt
    assert "background processing worker" not in prompt.lower()


def test_generate_opportunity_returns_expected_keys() -> None:
    items = _sample_items()
    score = score_opportunity(items, "GitHub Actions workflow debugging assistant")
    opportunity = generate_opportunity(
        "Developers need clearer GitHub Actions failure diagnosis",
        "4 related signals.",
        items,
        score,
    )

    for key in (
        "title",
        "problem_statement",
        "target_user",
        "current_workaround",
        "suggested_mvp",
        "why_now",
        "feasibility_score",
        "opportunity_score",
        "competition_notes",
        "generated_prompt",
        "common_phrases",
    ):
        assert key in opportunity
