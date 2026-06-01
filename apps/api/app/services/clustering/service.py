from __future__ import annotations

import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from uuid import UUID

THEME_TITLES = {
    "ai_code_audit": "AI-generated code needs production-readiness audits",
    "lead_radar": "Founders need a cheaper lead and community signal radar",
    "onboarding_dropoff": "Small SaaS teams need simple onboarding drop-off analysis",
    "ci_debugging": "Developers need clearer GitHub Actions failure diagnosis",
    "spreadsheet_report": "Operators need spreadsheet-to-client-report automation",
}
THEME_KEYWORDS = {
    "ai_code_audit": ["ai", "generated code", "tests", "duplicated", "error handling"],
    "lead_radar": ["reddit", "hacker news", "lead", "social listening", "founder"],
    "onboarding_dropoff": ["onboarding", "drop", "analytics", "events", "funnel"],
    "ci_debugging": ["github actions", "ci", "logs", "yaml", "workflow"],
    "spreadsheet_report": ["stripe", "csv", "spreadsheet", "report", "google sheets"],
}
MIN_CLUSTER_SIZE = 2
TITLE_STOP_WORDS = {
    "about",
    "after",
    "again",
    "because",
    "before",
    "being",
    "cannot",
    "could",
    "every",
    "having",
    "manual",
    "manually",
    "people",
    "should",
    "there",
    "these",
    "thing",
    "using",
    "where",
    "which",
    "while",
    "would",
}


@dataclass(frozen=True)
class ClusterCandidate:
    key: str
    title: str
    summary: str
    item_ids: list[UUID]
    centroid: list[float]


def infer_theme(text: str) -> str:
    lowered = text.lower()
    scores = {
        key: sum(1 for phrase in phrases if phrase in lowered) for key, phrases in THEME_KEYWORDS.items()
    }
    best, score = max(scores.items(), key=lambda pair: pair[1])
    return best if score > 0 else "misc"


def summarize(items: list[dict]) -> str:
    signals = Counter(item["signal_type"] for item in items)
    top_sources = Counter(item["source"] for item in items).most_common(2)
    return (
        f"{len(items)} related problem signals, mostly {signals.most_common(1)[0][0].replace('_', ' ')}. "
        f"Sources: {', '.join(source for source, _ in top_sources)}."
    )


def generic_title(items: list[dict]) -> str:
    words: Counter[str] = Counter()
    for item in items:
        text = f"{item['title']} {item['body']}".lower()
        for token in text.replace("-", " ").split():
            cleaned = token.strip(".,!?():;\"'[]{}")
            if len(cleaned) > 4 and cleaned not in TITLE_STOP_WORDS:
                words[cleaned] += 1
    topic = " ".join(word for word, _count in words.most_common(3))
    if not topic:
        return "Users need clearer repetitive workflow support"
    return f"Users need better {topic} workflows"


def mean_vector(item_ids: list[UUID], embeddings: dict[UUID, list[float]]) -> list[float]:
    if not item_ids:
        return []
    width = len(embeddings[item_ids[0]])
    return [
        round(sum(embeddings[item_id][index] for item_id in item_ids) / len(item_ids), 6)
        for index in range(width)
    ]


def dbscan_labels(items: list[dict], embeddings: dict[UUID, list[float]]) -> list[int]:
    if os.environ.get("TASKSIGNAL_USE_SKLEARN_CLUSTERING") != "1" or len(items) < 3:
        return [-1] * len(items)

    try:
        import numpy as np
        from sklearn.cluster import DBSCAN
    except Exception:  # pragma: no cover
        return [-1] * len(items)

    ids = [item["id"] for item in items]
    vectors = np.array([embeddings[item_id] for item_id in ids], dtype=float)
    return list(DBSCAN(eps=0.32, min_samples=3, metric="cosine").fit_predict(vectors))


def cluster_items(items: list[dict], embeddings: dict[UUID, list[float]]) -> list[ClusterCandidate]:
    if not items:
        return []

    labels = dbscan_labels(items, embeddings)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for index, item in enumerate(items):
        label = labels[index]
        if label >= 0:
            grouped[f"dbscan-{label}"].append(item)
        else:
            grouped[infer_theme(f"{item['title']} {item['body']}")].append(item)

    # Demo data is intentionally thematic; this fallback keeps local no-model runs useful.
    merged: dict[str, list[dict]] = defaultdict(list)
    generic_groups: list[tuple[str, list[dict]]] = []
    for group_key, group_items in grouped.items():
        theme = infer_theme(" ".join(f"{item['title']} {item['body']}" for item in group_items))
        if theme == "misc":
            generic_groups.append((group_key, group_items))
            continue
        merged[theme].extend(group_items)

    candidates: list[ClusterCandidate] = []
    for key, group_items in merged.items():
        if len(group_items) < MIN_CLUSTER_SIZE:
            continue
        group_ids = [item["id"] for item in group_items]
        candidates.append(
            ClusterCandidate(
                key=key,
                title=THEME_TITLES.get(key, group_items[0]["title"]),
                summary=summarize(group_items),
                item_ids=group_ids,
                centroid=mean_vector(group_ids, embeddings),
            )
        )
    for key, group_items in generic_groups:
        if len(group_items) < MIN_CLUSTER_SIZE:
            continue
        group_ids = [item["id"] for item in group_items]
        candidates.append(
            ClusterCandidate(
                key=key,
                title=generic_title(group_items),
                summary=summarize(group_items),
                item_ids=group_ids,
                centroid=mean_vector(group_ids, embeddings),
            )
        )
    return sorted(candidates, key=lambda cluster: len(cluster.item_ids), reverse=True)
