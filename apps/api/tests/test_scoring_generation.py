from datetime import UTC, datetime

from app.services.generation.service import generate_opportunity
from app.services.scoring.service import score_opportunity


def test_scoring_formula_and_prompt_generation() -> None:
    items = [
        {
            "source": "reddit",
            "title": "GitHub Actions logs are painful",
            "body": "Every week developers copy paste CI errors.",
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
    score = score_opportunity(items, "GitHub Actions workflow debugging assistant")
    opportunity = generate_opportunity(
        "Developers need clearer GitHub Actions failure diagnosis",
        "4 related signals.",
        items,
        score,
    )

    assert 0 < score["opportunity_score"] <= 1
    assert score["rank_drivers"]
    assert "Build" in opportunity["generated_prompt"]
    assert "Acceptance criteria" in opportunity["generated_prompt"]
    assert "Top source excerpts" in opportunity["generated_prompt"]
    assert "Every week developers copy paste CI errors." in opportunity["generated_prompt"]
    assert "Trust and privacy constraints" in opportunity["generated_prompt"]


def test_generated_prompt_keeps_author_identity_out_of_export() -> None:
    items = [
        {
            "source": "github",
            "title": "CI bot keeps failing on generated code",
            "body": "AliceExample says the generated code keeps missing tests.",
            "author": "AliceExample",
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

    assert "AliceExample" not in opportunity["generated_prompt"]
    assert "abc123hashedauthor" not in opportunity["generated_prompt"]
    assert "https://example.test/generated-code" in opportunity["generated_prompt"]
    assert "Generated code keeps missing tests." in opportunity["generated_prompt"]
