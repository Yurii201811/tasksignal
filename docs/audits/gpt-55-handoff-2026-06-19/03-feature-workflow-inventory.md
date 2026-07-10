# Feature And Workflow Inventory

## Implemented Workflows

### First-Run Demo

User can process bundled fixture data without API keys from the dashboard or smoke script. The verified smoke path loaded 18 raw items, detected 17 signals, generated 5 opportunities, and exported a task pack for the top opportunity.

Key files:

- `apps/api/app/workers/demo_pipeline.py`
- `scripts/first_run_smoke.py`
- `apps/web/src/features/dashboard.tsx`

### Public Live Scan

User can run public browser-safe scans through `POST /api/scans`. By default this includes `fixture` and `hackernews`. The API can narrow this with `PUBLIC_SCAN_SOURCES`.

Key files:

- `apps/api/app/api/routes.py`
- `apps/api/app/workers/scan_pipeline.py`
- `apps/api/app/services/ingestion/connectors.py`
- `apps/web/src/features/dashboard.tsx`
- `apps/web/src/features/scans.tsx`

### Saved Research Projects

User can save source, query, limit, cadence, labels, and enabled state. Projects can run manually or through due-run logic.

Key files:

- `apps/api/app/models/all_models.py`
- `apps/api/app/api/routes.py`
- `apps/web/src/features/research-projects.tsx`

### Local Workspace Profile

User can store local owner/focus/default workflow settings. This is a singleton local profile, not authentication.

Key files:

- `apps/api/app/models/all_models.py`
- `apps/api/app/api/routes.py`
- `apps/web/src/app/settings/page.tsx`

### Integrations And Readiness

User can inspect source/runtime/Codex handoff readiness without exposing secret values. The readiness payload includes project count, opportunity count, due project count, ready sources, public scan sources, and whether operator token is configured.

Key files:

- `apps/api/app/api/routes.py`
- `apps/web/src/app/settings/page.tsx`

### Opportunity Review

User can inspect score, evidence trail, source mix, rank drivers, score formula, common phrases, problem review, and evidence snippets.

Key files:

- `apps/api/app/api/routes.py`
- `apps/web/src/features/opportunity-detail.tsx`

### Prompt And Task-Pack Export

User can view, copy, and download generated Codex prompt Markdown. User can download evidence bundles and task packs.

Key files:

- `apps/api/app/api/routes.py`
- `apps/api/app/services/generation/service.py`
- `apps/web/src/features/prompt-view.tsx`
- `scripts/first_run_smoke.py`

### Semantic Evidence Search

User can search normalized evidence items by embedding similarity. Current API response shape includes `items` and `opportunities`, but `opportunities` is always an empty array.

Key files:

- `apps/api/app/api/routes.py`
- `apps/api/app/services/embeddings/service.py`
- `apps/web/src/features/search.tsx`

## Important Product Mismatches

### Prompt Enhancement Token Mismatch

The API requires `X-Operator-Scan-Token` for `POST /api/opportunities/{id}/enhance`. The current web API helper `enhanceOpportunity` does not accept or send the operator token, and the opportunity detail page calls it without token state. This means the "Enhance Prompt" action is likely unavailable from the UI in the intended gated configuration.

Suggested next action: wire the same local operator token used by Projects/Integrations into prompt enhancement, or hide/disable the button with clear readiness guidance when no token/runtime is configured.

### Semantic Search Opportunity Gap

`POST /api/search/semantic` returns ranked item hits and `opportunities: []`. The frontend only renders items. This is acceptable if intentional, but then the response type should be tightened. If opportunity search is desired, add opportunity retrieval and tests.

### Source Enabled State Needs Review

Sources expose `enabled`, and the Sources UI displays it. The scan path appears source-type driven and should be reviewed for whether disabled source records should block scans or whether `enabled` should be removed from user-facing semantics.

### Labels Are Minimal

`POST /api/labels` creates labels but does not yet power an evaluation/review workflow. This is a natural seed for v0.2 model-quality improvements.

## User-Facing Surfaces To Preserve

- First useful run checklist.
- Evidence trail and score breakdown.
- Scan detail for failed and zero-opportunity runs.
- Task-pack export with acceptance criteria and privacy constraints.
- Credential-safe integrations/readiness copy.
- Local-first language and single-machine workspace boundary.
