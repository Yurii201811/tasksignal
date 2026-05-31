from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path

from app.core.config import settings

THEMES = {
    "ai_code_audit": ["ai", "generated code", "tests", "duplicated", "error handling", "production ready"],
    "lead_radar": ["reddit", "hacker news", "leads", "social listening", "founder", "reply"],
    "onboarding_dropoff": ["onboarding", "drop off", "analytics", "events", "activation", "funnel"],
    "ci_debugging": ["github actions", "ci", "logs", "yaml", "workflow", "failed"],
    "spreadsheet_report": ["stripe", "csv", "spreadsheet", "client report", "google sheets", "export"],
}


def local_model_available(model_name: str) -> bool:
    model_path = Path(model_name).expanduser()
    if model_path.exists():
        return True

    cache_name = f"models--{model_name.replace('/', '--')}"
    candidates = []
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        candidates.append(Path(hf_home).expanduser() / "hub" / cache_name)
    candidates.append(Path.home() / ".cache" / "huggingface" / "hub" / cache_name)
    return any(path.exists() for path in candidates)


class EmbeddingService:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self._model = None
        if local_model_available(self.model_name):
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name, local_files_only=True)
                self.backend = "sentence-transformers"
            except Exception:
                self.backend = "deterministic-theme-fallback"
        else:
            self.backend = "deterministic-theme-fallback"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self._model is not None:
            vectors = self._model.encode(texts, normalize_embeddings=True)
            return [list(map(float, vector)) for vector in vectors]
        return [self._fallback_vector(text) for text in texts]

    def _fallback_vector(self, text: str) -> list[float]:
        lowered = text.lower()
        vector = [0.0] * 384
        for theme_index, phrases in enumerate(THEMES.values()):
            hits = sum(1 for phrase in phrases if phrase in lowered)
            vector[theme_index] = hits * 3.0

        tokens = re.findall(r"[a-z0-9]{3,}", lowered)
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            index = 16 + digest[0] % (384 - 16)
            vector[index] += 0.35

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return numerator / (left_norm * right_norm)
