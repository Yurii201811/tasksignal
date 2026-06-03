# API

Base URL: `http://localhost:8000`

## General

`GET /health`

Returns service status, selected LLM provider, embedding model, and fixture mode.

`GET /api/stats`

Returns item counts, source breakdown, and pain score distribution.

`GET /api/integrations`

Returns source, runtime, and Codex handoff readiness without returning secret
values. Credential fields are reported as environment variable names only.

`POST /api/integrations/{id}/test`

Runs a small connector readiness check. Credentialed source tests require
`X-Operator-Scan-Token` when `OPERATOR_SCAN_TOKEN` is configured. Runtime and
Codex handoff integrations return configuration status rather than making model
calls.

## Processing

`POST /api/process/demo`

Runs the full fixture pipeline without deleting existing data by default. The
demo processor deduplicates existing records, so repeated runs do not duplicate
normalized items, signals, clusters, or opportunities. Use `?reset=true` to
clear existing demo records before processing fixtures. When `DEMO_RESET_TOKEN`
is configured, reset requests must include `X-Demo-Reset-Token`.

Response:

```json
{
  "raw_items_loaded": 18,
  "normalized_items_created": 18,
  "signals_detected": 18,
  "clusters_created": 5,
  "opportunities_created": 5
}
```

`POST /api/scans`

Runs one synchronous live-source scan and stores a `ScanJob` with `queued`,
`running`, then `completed` or `failed` state. The endpoint fetches from the
selected connector, normalizes and deduplicates items, detects problem signals,
embeds matching items with the local embedding service or deterministic fallback,
clusters related signals, scores opportunities, and generates prompt-ready cards.
This public endpoint only accepts public API-safe sources (`fixture` and
`hackernews`). `PUBLIC_SCAN_SOURCES` can narrow that public allowlist further,
but it cannot enable credentialed connectors through this unauthenticated
endpoint.

Request:

```json
{
  "source": "hackernews",
  "query": "ask",
  "limit": 30
}
```

Public scan source values:

- `hackernews`: official Hacker News Firebase API. Query can be `ask`, `new`,
  `top`, `best`, `show`, or `job`; other query text filters the selected Ask HN
  feed client-side.
- `fixture`: fixture connector, mainly for local development; the primary demo
  path remains `POST /api/process/demo`.

Credentialed connectors remain available to trusted internal jobs that call the
scan pipeline directly:

- `github`: official GitHub Issues search API. `GITHUB_TOKEN` is optional but
  may expose private results visible to that token, so it is blocked from the
  public scan API.
- `stackexchange`: official Stack Exchange advanced search API for Stack
  Overflow. `STACK_EXCHANGE_KEY` is optional.
- `reddit`: official Reddit OAuth API. Requires `REDDIT_CLIENT_ID`,
  `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT`.

Response:

```json
{
  "id": "1d64d8e0-9d20-4e5e-bf7f-3f06e6c4c9e7",
  "source_id": "7aa8c017-9c5a-4908-a902-0a517460fe14",
  "source_type": "hackernews",
  "source_name": "Hacker News",
  "status": "completed",
  "query": "ask",
  "started_at": "2026-05-31T10:00:00Z",
  "finished_at": "2026-05-31T10:00:05Z",
  "error_message": null,
  "items_found": 30,
  "items_saved": 18
}
```

Failed live-source scans return the stored scan job with `status: "failed"` and
`error_message` populated so the dashboard can show the connector or credential
problem without losing the audit trail. Failed scan `error_message` values are
user-actionable and avoid echoing secrets or raw credential values. Messages
include connector-specific guidance for missing credentials, authorization
failures, and rate limits when applicable.

`GET /api/scans`

Returns recent scan jobs ordered by newest started timestamp first.

`GET /api/scans/{id}`

Returns one scan job with source, query, status, timestamps, found/saved counts,
and any stored redacted error message. The web scan detail page uses this
endpoint for completed, failed, queued, and running scan states.

## Research Projects

`GET /api/research-projects`

Returns saved repeatable research workflows ordered by most recently updated.

`POST /api/research-projects`

Creates a saved workflow.

Request:

```json
{
  "name": "Track CI/CD pain",
  "description": "Find repeated complaints that could become a focused developer-tool MVP.",
  "source_type": "hackernews",
  "query": "ask",
  "limit": 30,
  "cadence": "manual",
  "labels": ["ci", "developer-tools"],
  "enabled": true
}
```

`POST /api/research-projects/{id}/run`

Runs the saved source/query/limit and updates the project's `last_scan_id`.
Public scan sources follow the same allowlist as `POST /api/scans`.
Credentialed sources (`github`, `reddit`, `stackexchange`) require
`X-Operator-Scan-Token` matching `OPERATOR_SCAN_TOKEN` so browser-triggered
runs cannot silently spend server-side credentials.

## Opportunities

`GET /api/opportunities`

Returns ranked opportunity cards with evidence items.

`GET /api/opportunities/{id}`

Returns a single opportunity, scoring breakdown, and evidence.

The scoring breakdown includes raw component scores, weighted rank-driver notes,
the score formula, common phrases, and the explanation shown in the dashboard UI.
Evidence items include detector spans that support the ranking.

`GET /api/opportunities/{id}/prompt`

Returns the generated Markdown prompt. The prompt includes source excerpts,
ranking rationale, and privacy constraints so exported prompts remain auditable.

`GET /api/opportunities/{id}/export.md`

Downloads the prompt as Markdown.

`GET /api/opportunities/{id}/evidence.md`

Downloads a compact evidence bundle as Markdown. The bundle includes the
opportunity summary, score breakdown, rank drivers, evidence item titles,
detector excerpts, source URLs when safe, and caveats. It omits raw usernames,
author hashes, credential fields, and raw connector payloads.

`GET /api/opportunities/{id}/task-pack.json`

Returns a structured Codex task pack with objective, suggested MVP, generated
prompt, source URLs, acceptance criteria, and privacy constraints.

`GET /api/opportunities/{id}/task-pack.md`

Downloads the same task pack as Markdown for Codex, other coding agents, issue
drafting, or local review workflows.

## Search

`POST /api/search/semantic`

Request:

```json
{"query": "weekly spreadsheet report", "limit": 8}
```

## Sources, Scans, Labels

Current MVP endpoints include source list/create/update/delete, synchronous scan
create/list/read, and label create. Opportunities are generated by processing
pipelines and exposed through read/export/regenerate endpoints; scans and labels
do not have full CRUD in this release. Live scan scheduling remains an extension
point; the current MVP intentionally keeps scans synchronous and transparent.
