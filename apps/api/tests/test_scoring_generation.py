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
