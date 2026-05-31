# API

Base URL: `http://localhost:8000`

## General

`GET /health`

Returns service status, selected LLM provider, embedding model, and fixture mode.

`GET /api/stats`

Returns item counts, source breakdown, and pain score distribution.

## Processing

`POST /api/process/demo`

Runs the full fixture pipeline.

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

Request:

```json
{
  "source": "hackernews",
  "query": "ask",
  "limit": 30
}
```

Supported source values:

- `hackernews`: official Hacker News Firebase API. Query can be `ask`, `new`,
  `top`, `best`, `show`, or `job`; other query text filters the selected Ask HN
  feed client-side.
- `github`: official GitHub Issues search API. `GITHUB_TOKEN` is optional but
  recommended for higher rate limits. Query is passed to GitHub search, for
  example `is:issue is:open bug automation`.
- `stackexchange`: official Stack Exchange advanced search API for Stack
  Overflow. `STACK_EXCHANGE_KEY` is optional. Query searches question titles.
- `reddit`: official Reddit OAuth API. Requires `REDDIT_CLIENT_ID`,
  `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT`.
- `fixture`: fixture connector, mainly for local development; the primary demo
  path remains `POST /api/process/demo`.

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
problem without losing the audit trail.

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

## Search

`POST /api/search/semantic`

Request:

```json
{"query": "weekly spreadsheet report", "limit": 8}
```

## Sources, Scans, Labels

CRUD-style MVP endpoints exist for sources, scan records, and labels. Live scan
scheduling remains an extension point; the current MVP intentionally keeps scans
synchronous and transparent.
