# Architecture

TaskSignal is a local-first full-stack app with a fixture-powered demo path and optional live connectors.

## Module Responsibilities

- `services/ingestion`: connector interface, fixture loader, live source connectors, normalization, deduplication.
- `services/detection`: rule-based problem signal detection and evidence span extraction.
- `services/embeddings`: sentence-transformer embeddings with deterministic fallback.
- `services/clustering`: DBSCAN clustering plus local-demo thematic fallback.
- `services/scoring`: opportunity score components and explanation.
- `services/generation`: deterministic opportunity cards and Codex prompt generation.
- `workers`: process orchestration for demo and scheduled jobs.
- `api`: FastAPI endpoints.
- `apps/web`: Next.js dashboard and workflow UI.

## Data Flow

```mermaid
flowchart LR
  Fixtures --> Raw[raw_items]
  APIs --> Raw
  Raw --> Normalized[normalized_items]
  Normalized --> Signals[item_signals]
  Signals --> Embeddings[item_embeddings]
  Embeddings --> Clusters[clusters and cluster_items]
  Clusters --> Opportunities[opportunities]
  Opportunities --> Dashboard[Next.js dashboard]
```

## Local Deployment

Docker Compose starts Postgres with pgvector, the FastAPI API, and the Next.js frontend. `AUTO_CREATE_TABLES=true` keeps the local MVP simple; Alembic migrations are included for production-style evolution.

## Hosted Deployment

```mermaid
flowchart TD
  V[Vercel frontend] --> R[Render or Hugging Face backend]
  R --> S[(Supabase Postgres + pgvector)]
  G[GitHub Actions cron] --> R
```

