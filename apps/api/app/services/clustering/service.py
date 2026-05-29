from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from uuid import UUID

import numpy as np

try:
    from sklearn.cluster import DBSCAN
except Exception:  # pragma: no cover
    DBSCAN = None

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


def cluster_items(items: list[dict], embeddings: dict[UUID, list[float]]) -> list[ClusterCandidate]:
    if not items:
        return []

    ids = [item["id"] for item in items]
    vectors = np.array([embeddings[item_id] for item_id in ids], dtype=float)
    labels: list[int]
    if DBSCAN is not None and len(items) >= 3:
        labels = list(DBSCAN(eps=0.32, min_samples=3, metric="cosine").fit_predict(vectors))
    else:
        labels = [-1] * len(items)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for index, item in enumerate(items):
        label = labels[index]
        if label >= 0:
            grouped[f"dbscan-{label}"].append(item)
        else:
            grouped[infer_theme(f"{item['title']} {item['body']}")].append(item)

    # Demo data is intentionally thematic; this fallback keeps local no-model runs useful.
    merged: dict[str, list[dict]] = defaultdict(list)
    for group_items in grouped.values():
        theme = infer_theme(" ".join(f"{item['title']} {item['body']}" for item in group_items))
        if theme == "misc":
            continue
        merged[theme].extend(group_items)

    candidates: list[ClusterCandidate] = []
    for key, group_items in merged.items():
        if len(group_items) < 3:
            continue
        group_ids = [item["id"] for item in group_items]
        centroid = np.mean(np.array([embeddings[item_id] for item_id in group_ids]), axis=0)
        candidates.append(
            ClusterCandidate(
                key=key,
                title=THEME_TITLES.get(key, group_items[0]["title"]),
                summary=summarize(group_items),
                item_ids=group_ids,
                centroid=[round(float(value), 6) for value in centroid],
            )
        )
    return sorted(candidates, key=lambda cluster: len(cluster.item_ids), reverse=True)

