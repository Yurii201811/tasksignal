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

`GET /api/readiness`

Returns a compact operator-readiness summary with blockers, warnings, project
count, opportunity count, due-project count, ready public sources, and Codex
task-pack availability. It reports whether an operator scan token is configured
as a boolean only and never returns the token value.

`GET /api/local-workspace`

Returns the singleton local-machine workspace profile. This is not a user
account system; it stores the one local operator's owner/focus label and default
research workflow settings.

`PATCH /api/local-workspace`

Updates the singleton local workspace profile.

Request:

```json
{
  "owner_name": "Local Builder",
  "workspace_goal": "Find developer-tool opportunities",
  "default_source_type": "hackernews",
  "default_query": "ask",
  "default_limit": 30,
  "default_cadence": "daily",
  "default_schedule_interval_hours": null
}
```

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
endpoint. If the configured value excludes every browser-safe source, readiness
reports a warning and `POST /api/scans` returns a 403 with `Allowed public scan
sources: none` so operators can distinguish intentional lockdown from a broken
connector.

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
  "items_saved": 18,
  "signals_detected": 4,
  "clusters_created": 1,
  "opportunities_created": 1,
  "outcome_message": "The scan generated 1 ranked opportunity from 4 detected signals."
}
```

Completed live-source scans can still create zero opportunities. In that case,
`status` remains `completed`, found/saved counts remain available, and
`outcome_message` explains whether the run had no returned records, duplicate
records, no detected problem signals, or signals that were too unrelated to form
a ranked opportunity.

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
signal counts, generated opportunity counts, outcome guidance, and any stored
redacted error message. The web scan detail page uses this endpoint for
completed, zero-opportunity, failed, queued, and running scan states.

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
  "schedule_interval_hours": null,
  "labels": ["ci", "developer-tools"],
  "enabled": true
}
```

`POST /api/research-projects/{id}/run`

Runs the saved source/query/limit and updates the project's `last_scan_id`,
`last_run_at`, `next_run_at`, and `run_count`. Public scan sources follow the
same allowlist as `POST /api/scans`. Credentialed sources (`github`, `reddit`,
`stackexchange`) require `X-Operator-Scan-Token` matching `OPERATOR_SCAN_TOKEN`
so browser-triggered runs cannot silently spend server-side credentials.

Cadence values `hourly`, `daily`, and `weekly` set `next_run_at` automatically.
Use `cadence: "custom"` plus `schedule_interval_hours` for another interval.
Use `cadence: "manual"` or a null interval for unscheduled workflows.

`POST /api/research-projects/run-due`

Runs every enabled saved project whose `next_run_at` is due. Projects that need
an operator token are skipped when the request lacks a valid
`X-Operator-Scan-Token`.

Response:

```json
{
  "ran": 1,
  "skipped": 0,
  "scans": []
}
```

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

`POST /api/opportunities/{id}/enhance?apply=false`

Optionally improves the generated build prompt through the configured model
runtime. This endpoint is disabled unless `LLM_PROVIDER=openai` with
`OPENAI_API_KEY`, or `LLM_PROVIDER=ollama` with a reachable local Ollama server,
is configured. With `apply=true`, the enhanced prompt replaces the stored
generated prompt.

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

Current MVP endpoints include singleton local workspace settings, source
list/create/update/delete, synchronous scan create/list/read, saved research
project create/list/read/run/run-due, and label create. Opportunities are
generated by processing pipelines and exposed through read/export/regenerate/
enhance endpoints; scans and labels do not have full CRUD in this release.
Scheduling is explicit through `run-due` so operators can use cron, GitHub
Actions, a worker, or the local CLI without hiding background jobs inside the web
process.
