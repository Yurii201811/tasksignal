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

## Opportunities

`GET /api/opportunities`

Returns ranked opportunity cards with evidence items.

`GET /api/opportunities/{id}`

Returns a single opportunity, scoring breakdown, and evidence.

`GET /api/opportunities/{id}/prompt`

Returns the generated Markdown prompt.

`GET /api/opportunities/{id}/export.md`

Downloads the prompt as Markdown.

## Search

`POST /api/search/semantic`

Request:

```json
{"query": "weekly spreadsheet report", "limit": 8}
```

## Sources, Scans, Labels

CRUD-style MVP endpoints exist for sources, scan records, and labels. Live connector scheduling is documented as an extension point.

