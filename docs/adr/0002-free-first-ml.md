# ADR 0002: Free-First ML

TaskSignal does not require paid LLM APIs. The default provider is `none`.

Embeddings use sentence-transformers when locally available, with deterministic fallback vectors for offline runs. Summaries and prompts use extractive/template generation by default.

