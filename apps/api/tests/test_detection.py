from app.services.detection.rules import detect_problem_signal


def test_detector_prioritizes_concrete_repetitive_tasks() -> None:
    result = detect_problem_signal(
        "Weekly Stripe report is painful",
        "Every Friday I manually export Stripe payments, import a CSV into Google Sheets, and send a client report.",
    )

    assert result.is_problem_signal is True
    assert result.signal_type in {"manual_workflow", "buying_intent", "tool_request"}
    assert result.task_concreteness_score > 0.5
    assert result.evidence_spans


def test_detector_rejects_vague_complaints() -> None:
    result = detect_problem_signal("Productivity is hard", "I hate dashboards.")

    assert result.is_problem_signal is False

