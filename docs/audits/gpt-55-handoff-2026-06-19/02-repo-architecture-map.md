# Repo And Architecture Map

## Top-Level Structure

- `apps/api` - FastAPI backend, SQLAlchemy models, ingestion, detection, clustering, scoring, generation, tests.
- `apps/web` - Next.js app with dashboard, projects, sources, scans, search, settings, opportunities, and prompt views.
- `data/fixtures` - credential-free public-style sample data.
- `docs` - architecture, API, ethics, model card, roadmap, deployment, release, threat model, and demo evidence.
- `scripts` - doctor, smoke proof, release check, fixture redaction, CLI.
- `skills/tasksignal-opportunity-builder` - Codex-style skill for converting TaskSignal task packs into downstream plans.

## Runtime Architecture

Source files:

- `docs/architecture.md`
- `apps/api/app/api/routes.py`
- `apps/api/app/workers/scan_pipeline.py`
- `apps/api/app/workers/demo_pipeline.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/components/app-shell.tsx`

Data flow:

1. Fixture or official public API connector fetches raw records.
2. Normalizer cleans text, hashes authors, preserves safe source URLs, deduplicates by text hash.
3. Detector assigns signal type, pain score, task concreteness, buying intent, and evidence spans.
4. Embedding service uses local sentence-transformer if available, otherwise deterministic fallback vectors.
5. Clustering groups related problem signals using optional DBSCAN or thematic fallback.
6. Scoring combines frequency, recency, pain, task concreteness, buying intent, feasibility, and competition penalty.
7. Generator creates opportunity cards, prompts, evidence bundles, and task packs.
8. FastAPI exposes read, scan, export, readiness, and operator-gated actions.
9. Next.js renders dashboard, saved projects, scans, integrations, search, opportunity detail, and prompt export flows.

## API Surface

High-signal endpoints from `docs/api.md` and `apps/api/app/api/routes.py`:

- `GET /health`
- `GET /api/stats`
- `GET /api/integrations`
- `GET /api/readiness`
- `GET/PATCH /api/local-workspace`
- `POST /api/process/demo`
- `POST /api/scans`
- `GET /api/scans`
- `GET /api/scans/{id}`
- `GET/POST /api/research-projects`
- `POST /api/research-projects/{id}/run`
- `POST /api/research-projects/run-due`
- `GET /api/opportunities`
- `GET /api/opportunities/{id}`
- `GET /api/opportunities/{id}/prompt`
- `POST /api/opportunities/{id}/regenerate`
- `POST /api/opportunities/{id}/enhance`
- `GET /api/opportunities/{id}/export.md`
- `GET /api/opportunities/{id}/evidence.md`
- `GET /api/opportunities/{id}/task-pack.json`
- `GET /api/opportunities/{id}/task-pack.md`
- `POST /api/search/semantic`
- `POST /api/labels`

## Data Model

Source file: `apps/api/app/models/all_models.py`

Key tables:

- `sources`
- `scan_jobs`
- `research_projects`
- `local_workspace_settings`
- `raw_items`
- `normalized_items`
- `item_signals`
- `item_embeddings`
- `clusters`
- `cluster_items`
- `opportunities`
- `labels`

Important model choices:

- `LocalWorkspaceSettings` is a singleton, not a user account system.
- `NormalizedItem.author_hash` stores hashed author identity.
- Embeddings use `pgvector` when not SQLite, JSON fallback for SQLite/tests.
- `ScanJob` stores counts and `outcome_message` for completed, failed, and zero-opportunity cases.

## Frontend Map

Source files:

- `apps/web/src/features/dashboard.tsx`
- `apps/web/src/features/research-projects.tsx`
- `apps/web/src/features/scans.tsx`
- `apps/web/src/features/scan-detail.tsx`
- `apps/web/src/features/sources.tsx`
- `apps/web/src/features/search.tsx`
- `apps/web/src/features/opportunity-detail.tsx`
- `apps/web/src/features/prompt-view.tsx`
- `apps/web/src/app/settings/page.tsx`

Routes:

- `/` - home entry
- `/dashboard` - first useful run, fixture/demo and live public scan loop
- `/projects` - saved research workflows
- `/sources` - source registry/readiness
- `/scans` - scan history
- `/scans/[id]` - scan detail
- `/search` - semantic evidence search
- `/settings` - local workspace and integrations
- `/opportunities/[id]` - opportunity detail, evidence, score, exports
- `/opportunities/[id]/prompt` - generated prompt preview/export

## Trust Boundaries

- Public unauthenticated scan API is restricted to `fixture` and `hackernews` unless narrowed further.
- Credentialed browser-triggered scans require `OPERATOR_SCAN_TOKEN`.
- Source registry mutations require `OPERATOR_SCAN_TOKEN`.
- Prompt enhancement requires `OPERATOR_SCAN_TOKEN` and explicit model provider configuration.
- Source configs are redacted on reads and reject secret-like keys on create/update.
- Evidence/task-pack exports omit raw usernames, author hashes, credential fields, and raw connector payloads.
