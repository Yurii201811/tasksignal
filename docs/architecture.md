# Architecture

TaskSignal is a local-first full-stack app for one local operator on one machine, with fixture data, optional live connectors, saved research workflows, and agent handoff exports.

## Module Responsibilities

- `services/ingestion`: connector interface, fixture loader, live source connectors, normalization, deduplication.
- `services/detection`: rule-based problem signal detection and evidence span extraction.
- `services/embeddings`: sentence-transformer embeddings when a local model cache exists, with deterministic fallback.
- `services/clustering`: local thematic clustering fallback by default, with optional DBSCAN when `TASKSIGNAL_USE_SKLEARN_CLUSTERING=1`.
- `services/scoring`: opportunity score components and explanation.
- `services/generation`: deterministic opportunity cards, Codex prompt generation, and optional runtime-backed prompt enhancement.
- `services/evidence_review`: append-only evidence-review snapshots, evidence readiness, and selection-biased evaluation summaries.
- `workers`: process orchestration for fixture processing and explicit scan jobs.
- `workers.scan_pipeline`: synchronous live-source scan orchestration for one
  selected source/query/limit without a background job framework.
- `api`: FastAPI endpoints.
- `apps/web`: Next.js dashboard, singleton local workspace settings, saved research projects, integrations, and workflow UI.
- `skills/tasksignal-opportunity-builder`: Codex-style skill package for
  turning TaskSignal task packs into PRDs, issues, implementation plans, or
  evidence reviews.

## Data Flow

Decision-workbench flow: opportunity evidence → `evidence_review` service →
readiness/evaluation → API → dashboard/detail/Evaluation/exports.

```mermaid
flowchart LR
  Fixtures --> Raw[raw_items]
  APIs --> Raw
  Raw --> Normalized[normalized_items]
  Normalized --> Signals[item_signals]
  Signals --> Embeddings[item_embeddings]
  Embeddings --> Clusters[clusters and cluster_items]
  Clusters --> Opportunities[opportunities]
  Opportunities --> Evidence[Opportunity evidence]
  Evidence --> Review[Evidence review service]
  Review --> Metrics[Readiness and evaluation]
  Metrics --> API[FastAPI API]
  API --> Workbench[Dashboard, detail, and Evaluation]
  API --> Exports[Evidence bundles and Codex task packs]
  Workspace[Local workspace profile] --> Projects
  Projects[Saved research projects] --> APIs
  Scheduler[CLI, cron, worker, or GitHub Actions] --> Projects
```

## Local Deployment

Docker Compose starts Postgres with pgvector, the FastAPI API, and the Next.js frontend, publishing all three host ports on `127.0.0.1` by default. `AUTO_CREATE_TABLES=true` creates missing tables for the local MVP but does not migrate an existing PostgreSQL schema; Alembic migrations are included for migration-managed evolution.

Scheduling is explicit: the API stores `next_run_at` and `run_count`, while the
Projects page, CLI, cron, GitHub Actions, or another worker calls
`POST /api/research-projects/run-due`. The web process does not contain a hidden
background scheduler.

The local workspace profile is a singleton row, not a multi-user identity
system. It stores the local operator's owner/focus label and project defaults for
the machine running TaskSignal.

## Hosted Deployment

```mermaid
flowchart TD
  V[Vercel frontend] --> R[Render or Hugging Face backend]
  R --> S[(Supabase Postgres + pgvector)]
  G[GitHub Actions cron] --> R
```
