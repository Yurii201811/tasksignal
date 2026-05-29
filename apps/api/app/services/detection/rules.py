from __future__ import annotations

import re
from dataclasses import dataclass

PAIN_PHRASES = [
    "hate",
    "annoying",
    "frustrating",
    "sucks",
    "painful",
    "tired of",
    "takes forever",
    "hard to",
    "struggling with",
    "why is this so hard",
    "wasting time",
    "nightmare",
    "broken workflow",
    "impossible to manage",
    "too much manual work",
]
TASK_PHRASES = [
    "every day",
    "every week",
    "every month",
    "manually",
    "copy paste",
    "copy-paste",
    "spreadsheet",
    "report",
    "workflow",
    "repeat",
    "automate",
    "script",
    "export",
    "import",
    "sync",
    "reconcile",
    "review",
    "audit",
    "check every time",
]
TOOL_REQUEST_PHRASES = [
    "is there a tool",
    "any tool",
    "alternative to",
    "how do i",
    "what do you use",
    "wish there was",
    "looking for",
    "can someone recommend",
    "best way to",
    "how are people doing",
    "does anyone know",
]
BUYING_INTENT_PHRASES = [
    "would pay",
    "paid tool",
    "pricing",
    "subscription",
    "budget",
    "client",
    "business",
    "invoice",
    "revenue",
    "customer",
    "team needs",
    "boss asked",
    "company uses",
    "paid plan",
]
CONCRETENESS_HINTS = [
    "stripe",
    "github actions",
    "google sheets",
    "csv",
    "every monday",
    "every friday",
    "minutes",
    "hours",
    "dashboard",
    "client report",
    "logs",
    "yaml",
    "onboarding",
    "events",
    "reddit",
    "hacker news",
]


@dataclass(frozen=True)
class DetectionResult:
    is_problem_signal: bool
    signal_type: str
    pain_score: float
    task_concreteness_score: float
    buying_intent_score: float
    evidence_spans: list[str]


def phrase_score(text: str, phrases: list[str], weight: float = 0.2) -> float:
    hits = sum(1 for phrase in phrases if phrase in text)
    return min(hits * weight, 1.0)


def evidence_spans(text: str) -> list[str]:
    phrases = PAIN_PHRASES + TASK_PHRASES + TOOL_REQUEST_PHRASES + BUYING_INTENT_PHRASES
    sentences = re.split(r"(?<=[.!?])\s+", text)
    spans = [s.strip() for s in sentences if any(phrase in s.lower() for phrase in phrases)]
    return spans[:4]


def detect_problem_signal(title: str, body: str) -> DetectionResult:
    text = f"{title}. {body}".lower()
    pain = phrase_score(text, PAIN_PHRASES, 0.22)
    task = min(phrase_score(text, TASK_PHRASES, 0.16) + phrase_score(text, CONCRETENESS_HINTS, 0.09), 1.0)
    tool = phrase_score(text, TOOL_REQUEST_PHRASES, 0.24)
    buying = phrase_score(text, BUYING_INTENT_PHRASES, 0.18)
    spans = evidence_spans(f"{title}. {body}")

    if "would pay" in text or buying >= 0.35:
        signal_type = "buying_intent"
    elif tool >= 0.35:
        signal_type = "tool_request"
    elif task >= 0.45:
        signal_type = "manual_workflow"
    elif "workaround" in text or "copy paste" in text:
        signal_type = "workaround"
    elif pain >= 0.35:
        signal_type = "complaint"
    elif "confusing" in text or "how do i" in text:
        signal_type = "confusion"
    else:
        signal_type = "not_relevant"

    combined = pain * 0.45 + task * 0.35 + tool * 0.1 + buying * 0.1
    is_signal = combined >= 0.22 and task >= 0.18
    return DetectionResult(
        is_problem_signal=is_signal,
        signal_type=signal_type if is_signal else "not_relevant",
        pain_score=round(min(pain + (0.1 if task > 0.5 else 0), 1.0), 3),
        task_concreteness_score=round(task, 3),
        buying_intent_score=round(buying, 3),
        evidence_spans=spans,
    )

