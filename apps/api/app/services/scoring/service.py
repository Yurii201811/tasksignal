from __future__ import annotations

from datetime import UTC, datetime

GENERIC_COMPETITION = ["todo", "crm", "project management", "note-taking", "social network"]
FEASIBLE_TERMS = [
    "api",
    "dashboard",
    "automation",
    "browser",
    "report",
    "scanner",
    "github",
    "spreadsheet",
]
LOW_FEASIBILITY = ["medical", "legal", "hardware", "marketplace", "regulated"]
SCORE_COMPONENTS = [
    ("frequency", "Frequency", 0.25),
    ("recency", "Recency", 0.20),
    ("pain_intensity", "Pain intensity", 0.20),
    ("task_concreteness", "Task concreteness", 0.15),
    ("buying_intent", "Buying intent", 0.10),
    ("feasibility", "Feasibility", 0.10),
    ("competition_penalty", "Competition penalty", -0.10),
]


def clamp(value: float) -> float:
    return round(max(0.0, min(value, 1.0)), 3)


def recency_score(created_dates: list[datetime]) -> float:
    if not created_dates:
        return 0.5
    now = datetime.now(UTC)
    normalized = [date if date.tzinfo else date.replace(tzinfo=UTC) for date in created_dates]
    avg_days = sum((now - date).days for date in normalized) / len(normalized)
    return clamp(1 - (avg_days / 730))


def feasibility_score(text: str) -> float:
    lowered = text.lower()
    score = 0.55 + 0.08 * sum(1 for term in FEASIBLE_TERMS if term in lowered)
    score -= 0.18 * sum(1 for term in LOW_FEASIBILITY if term in lowered)
    return clamp(score)


def competition_penalty(text: str) -> float:
    lowered = text.lower()
    return clamp(0.18 * sum(1 for term in GENERIC_COMPETITION if term in lowered))


def score_drivers(components: dict[str, float]) -> list[str]:
    drivers: list[tuple[float, str]] = []
    for key, label, weight in SCORE_COMPONENTS:
        value = components[key]
        contribution = value * weight
        if key == "competition_penalty" and value == 0:
            drivers.append((0, "Competition penalty did not reduce the score."))
            continue
        drivers.append(
            (abs(contribution), f"{label} contributed {contribution * 100:+.1f} weighted points.")
        )
    return [driver for _impact, driver in sorted(drivers, reverse=True)[:3]]


def score_opportunity(items: list[dict], candidate_text: str) -> dict:
    frequency = clamp(len(items) / 20)
    recency = recency_score([item["created_at"] for item in items])
    pain = clamp(sum(item["pain_score"] for item in items) / len(items))
    task = clamp(sum(item["task_concreteness_score"] for item in items) / len(items))
    buying = clamp(sum(item["buying_intent_score"] for item in items) / len(items))
    feasible = feasibility_score(candidate_text)
    penalty = competition_penalty(candidate_text)
    total = clamp(
        0.25 * frequency
        + 0.20 * recency
        + 0.20 * pain
        + 0.15 * task
        + 0.10 * buying
        + 0.10 * feasible
        - 0.10 * penalty
    )
    components = {
        "frequency": frequency,
        "recency": recency,
        "pain_intensity": pain,
        "task_concreteness": task,
        "buying_intent": buying,
        "feasibility": feasible,
        "competition_penalty": penalty,
    }
    return {
        **components,
        "opportunity_score": total,
        "rank_drivers": score_drivers(components),
        "score_formula": (
            "0.25*frequency + 0.20*recency + 0.20*pain + 0.15*task "
            "+ 0.10*buying + 0.10*feasibility - 0.10*competition"
        ),
        "explanation": (
            f"Score combines {len(items)} matching signals, average pain {pain:.2f}, "
            f"task concreteness {task:.2f}, buying intent {buying:.2f}, and feasibility {feasible:.2f}."
        ),
    }
