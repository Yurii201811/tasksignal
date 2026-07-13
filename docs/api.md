# API Reference

Base URL: `http://127.0.0.1:8000`

## Versioning and Protection

`/api/v1` is the canonical REST prefix. The same route set remains available
under `/api` as a compatibility alias throughout v1.x, but only `/api/v1` is
included in the generated OpenAPI schema. New clients should not use the legacy
prefix.

`GET /health` is outside the versioned API and returns process health plus the
selected model configuration.

TaskSignal is a single-operator service, not a user-authentication system. Some
sensitive operator routes always require `X-Operator-Scan-Token` matching
`OPERATOR_SCAN_TOKEN`. A hosted preview can additionally set
`REQUIRE_OPERATOR_TOKEN_FOR_ALL_API=true` to protect every `/api/` request, or
`REQUIRE_OPERATOR_TOKEN_FOR_WRITES=true` to protect every mutating request.
Neither setting provides accounts, tenant isolation, or per-user authorization.

## Common Response Types

The primary v1 response models are:

- `ResearchRunOut`: an immutable project-run snapshot and scan counters.
- `RunDeltaOut`: evidence, signal, generated-snapshot, and opportunity-thread
  changes relative to the prior complete run.
- `OpportunityThreadOut`: persistent decision state, current snapshot, immutable
  snapshot history, and append-only decision history.
- `SemanticSearchOut`: safe evidence hits and related opportunity-thread hits.
- `BuildPacketOut`: packet metadata, manifest, and immutable artifacts.
- `AgentSessionOut`: process-bound approval and lease state.
- `AgentActionOut`: a redacted append-only agent action event.

All timestamps are UTC JSON datetimes. IDs are UUIDs.

## General and Local Workspace

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health and selected model configuration. |
| `GET` | `/api/v1/stats` | Item counts, source breakdown, and pain distribution. |
| `GET` | `/api/v1/integrations` | Redacted source/runtime/Codex readiness. |
| `POST` | `/api/v1/integrations/{id}/test` | Small connector or runtime readiness check. Credentialed sources require the operator token. |
| `GET` | `/api/v1/readiness` | Operator blockers, warnings, counts, and public-source readiness. |
| `GET` | `/api/v1/local-workspace` | Singleton local-machine workspace profile. |
| `PATCH` | `/api/v1/local-workspace` | Update the singleton local workspace profile. |

The local workspace is convenience metadata for one operator. It is not an
account or authorization boundary.

## Sources and Discourse Authorization

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/sources` | List source metadata with `config_json` redacted. |
| `POST` | `/api/v1/sources` | Create a source. Requires the operator token. |
| `PATCH` | `/api/v1/sources/{source_id}` | Update a source without changing its connector type. Requires the operator token. |
| `DELETE` | `/api/v1/sources/{source_id}` | Delete an unreferenced source. Requires the operator token. |
| `GET` | `/api/v1/sources/{source_id}/authorization` | Read one Discourse source's exact-origin authorization state. |
| `PUT` | `/api/v1/sources/{source_id}/authorization` | Confirm terms and authorize one exact HTTPS origin. Requires the operator token. |
| `DELETE` | `/api/v1/sources/{source_id}/authorization` | Revoke Discourse terms/origin authorization. Requires the operator token. |
| `GET` | `/api/v1/sources/{source_id}/runtime-state` | Read readiness, last success, sanitized last failure, HTTP status, and `Retry-After` state. |

Discourse authorization accepts:

```json
{
  "origin": "https://community.example.com",
  "terms_confirmed": true
}
```

The origin must be an exact HTTPS origin without credentials, path, query, or
fragment. IP literals, numeric IP forms, localhost, private/loopback/link-local
DNS results, and cross-host redirects are rejected. The connector does not send
cookies or user credentials and does not support private categories. Its
timeouts, response bytes, redirects, and result count are bounded. Authorization
is a human/operator operation and is deliberately absent from MCP.

Source registry payloads reject secret-like keys. Connector credentials remain
environment variables and are never returned by source reads.

## Scans and Processing

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/process/demo` | Run the fixture pipeline; repeated non-reset runs deduplicate stored evidence. |
| `POST` | `/api/v1/scans` | Run one synchronous public scan. |
| `GET` | `/api/v1/scans` | List scan jobs, newest first. |
| `GET` | `/api/v1/scans/{scan_id}` | Read status, counts, outcome, and sanitized failure state. |

The unauthenticated `POST /scans` surface accepts only `fixture` and
`hackernews`; `PUBLIC_SCAN_SOURCES` can narrow that set but cannot add a
credentialed source. Reddit, GitHub Issues, Stack Exchange, and Discourse run
through trusted project/operator paths.

Example:

```json
{
  "source": "hackernews",
  "query": "ask",
  "limit": 30
}
```

A completed scan can create zero opportunities. Its outcome distinguishes no
records, already-stored evidence, no problem signals, and signals that did not
form a ranked cluster. A failed scan retains a sanitized audit record.

## Research Projects, Runs, and Deltas

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/research-projects` | List saved projects. |
| `POST` | `/api/v1/research-projects` | Create a repeatable source/query/limit workflow. |
| `GET` | `/api/v1/research-projects/{project_id}` | Read one project and its optimistic-lock version. |
| `PATCH` | `/api/v1/research-projects/{project_id}` | Update selected fields with optional `expected_version`. |
| `POST` | `/api/v1/research-projects/{project_id}/run` | Run one enabled project. |
| `POST` | `/api/v1/research-projects/run-due` | Run every enabled due project that the caller is authorized to run. |
| `GET` | `/api/v1/research-projects/{project_id}/runs` | List immutable run snapshots, newest first. |
| `GET` | `/api/v1/research-projects/{project_id}/runs/{run_id}/delta` | Compare one complete run with its prior complete run. |

Create example:

```json
{
  "name": "Track CI/CD pain",
  "description": "Repeated public problems that could become a focused tool.",
  "source_type": "hackernews",
  "source_id": null,
  "query": "ask",
  "limit": 30,
  "cadence": "manual",
  "schedule_interval_hours": null,
  "labels": ["ci", "developer-tools"],
  "enabled": true
}
```

Project runs snapshot source type/origin, query, requested limit, scan linkage,
and all observed items. Only missing evidence records are stored, detected, and
embedded, while clustering can reuse all signal-bearing evidence observed by
that run. Repeating an identical scan therefore creates an auditable run without
duplicating evidence or manufacturing a new thread.

Delta counts use precise terms:

- `new`: evidence first stored by this scan.
- `seen_before`: evidence already stored and observed again.
- `updated`: the same stable source identity now has different content.
- `unchanged`: the same stable source identity has the same content.
- `not_observed_this_run` (shown as “not observed this run”): present in the
  prior comparison set but absent now; this never means deleted, resolved, or
  no longer important.

Legacy run lineage is reported as `untracked`. The API returns `409` rather than
inferring a comparison from timestamps. Failed or incomplete runs likewise
cannot produce a trusted delta.

Credentialed project runs and every Discourse project run require the operator
token. Discourse projects must also reference an authorized, ready source.

## Opportunity Threads

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/opportunity-threads` | List persistent threads, optionally filtered by `project_id` and `review_state`. |
| `GET` | `/api/v1/opportunity-threads/{thread_id}` | Read current decision state, snapshots, match provenance, and decision history. |
| `PATCH` | `/api/v1/opportunity-threads/{thread_id}/decision` | Set a human decision with `expected_version`. |
| `POST` | `/api/v1/opportunity-threads/{thread_id}/snapshots/{snapshot_id}/detach` | Human-only correction that moves an auto-matched snapshot to a new thread. |

Decision request:

```json
{
  "review_state": "build_candidate",
  "review_note": "Local note excluded from exports",
  "expected_version": 4
}
```

Review states are `new`, `needs_more_evidence`, `promising`, `rejected`,
`duplicate`, and `build_candidate`.

Matching never crosses project boundaries. An exact evidence-set hash is an
immediate match unless multiple candidates make it ambiguous. Otherwise the
service compares only matching embedding model/backend identities and scores:

```text
0.60 * centroid similarity
+ 0.25 * evidence Jaccard
+ 0.15 * normalized-title Jaccard
```

Automatic matching requires a score of at least `0.82` and a margin of at least
`0.05` over the next candidate. The response exposes match method, confidence,
margin, component scores, evidence/content hashes, and model/backend metadata.

The older snapshot/export routes remain available during v1.x:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/opportunities` | List ranked snapshots with deterministic score/newest/ID ordering. Optional queue filters are described below. |
| `GET` | `/api/v1/opportunities/{opportunity_id}` | Read one snapshot, score breakdown, readiness, and evidence. |
| `PATCH` | `/api/v1/opportunities/{opportunity_id}/review` | Legacy decision update; current thread state remains authoritative. |
| `POST` | `/api/v1/opportunities/{opportunity_id}/regenerate` | Regenerate the deterministic legacy prompt. |
| `POST` | `/api/v1/opportunities/{opportunity_id}/enhance` | Optional configured-model prompt enhancement; requires the operator token. |
| `GET` | `/api/v1/opportunities/{opportunity_id}/prompt` | Read the generated Markdown prompt. |
| `GET` | `/api/v1/opportunities/{opportunity_id}/export.md` | Download the generated prompt. |
| `GET` | `/api/v1/opportunities/{opportunity_id}/evidence.md` | Download a redacted evidence bundle. |
| `GET` | `/api/v1/opportunities/{opportunity_id}/task-pack.json` | Read the legacy structured task pack. |
| `GET` | `/api/v1/opportunities/{opportunity_id}/task-pack.md` | Download the legacy Markdown task pack. |

New decision and build workflows should use opportunity threads and immutable
build packets.

The opportunity queue keeps historical snapshots as its compatibility default.
Pass `current_only=true` for one current snapshot per thread, as the dashboard
does. The filters `review_state`, `project_id`, `evidence_source`, `readiness`,
and `max_age_days` compose server-side. `evidence_source` matches any linked
evidence source type, not a configured host or only the displayed top source;
`readiness` is derived from current human review state; and `max_age_days` must
be between 1 and 3650 and applies to snapshot creation time. The dashboard's
Review next action opens the first deterministic result whose thread remains in
the `new` decision state within the active project/source/readiness/age scope.

## Semantic Search

`POST /api/v1/search`

`POST /api/v1/search/semantic` remains a hidden compatibility alias.

Request:

```json
{
  "query": "weekly spreadsheet report",
  "limit": 8,
  "project_id": null,
  "source": null,
  "signal_type": null,
  "review_state": null
}
```

The response has `evidence_hits` and `opportunity_threads`. Evidence hits contain
a bounded safe excerpt, match score, safe URL, signal/review state, evidence
hash, and observed scan/run/project provenance. Thread hits add readiness,
decision state, current snapshot provenance, and matched evidence IDs.

Search never returns raw connector JSON, author hashes, local review notes,
credentials, or source configuration. Source text is marked as untrusted
evidence. Only embeddings with the active model/backend identity participate.

## Evidence Review and Evaluation

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/labels` | Append a human evidence label, optionally with `expected_version`. |
| `GET` | `/api/v1/items/{item_id}/labels` | Return complete newest-first human/agent label history. |
| `GET` | `/api/v1/evaluation` | Return human-confirmed coverage and selection-biased precision summaries. |

Recognized labels are `true_signal`, `false_positive`, `unclear`, `duplicate`,
`not_actionable`, and `sensitive_risk`. Labels store `actor_type`; agent labels
also retain session provenance. Human readiness and precision calculations use
human-confirmed labels so an agent cannot grade its own work.

## Immutable Build Packets

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/opportunity-threads/{thread_id}/build-packets` | Create one immutable packet. |
| `GET` | `/api/v1/opportunity-threads/{thread_id}/build-packets` | List packet summaries with pagination. |
| `GET` | `/api/v1/build-packets/{packet_id}` | Read packet metadata, manifest, and artifacts. |
| `GET` | `/api/v1/build-packets/{packet_id}/verify` | Verify inventory, hashes, metadata, decision, and source-snapshot lineage. |
| `GET` | `/api/v1/build-packets/{packet_id}/download` | Download a deterministic ZIP only after verification passes. |

Create request:

```json
{
  "expected_version": 4,
  "use_configured_ai": false
}
```

Eligibility requires the current thread to be `build_candidate`, medium or
strong evidence readiness, and no current `sensitive_risk`. The deterministic
packet contains nine authoritative artifacts plus `MANIFEST.json`:

```text
README.md
MANIFEST.json
opportunity.json
evidence.md
task-pack.md
product-requirements.md
validation-plan.md
github-issue.md
implementation-plan.md
agent-brief.md
```

The manifest hashes and counts the other nine files; its separately stored digest
avoids a recursive self-hash. Optional configured-AI generation requires the
operator token. Validated `enhanced/` variants may be included, but deterministic
originals remain authoritative and fallback metadata is retained. Packet
creation rechecks eligibility before commit to prevent a concurrent decision or
snapshot change from slipping through.

The packet excludes local decision notes, raw identities, raw connector payloads,
and secrets. `github-issue.md` is a draft artifact only; no external issue is
created.

## Agent Sessions and Audit

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/agent-sessions` | Register one stdio process using a SHA-256 secret hash. |
| `GET` | `/api/v1/agent-sessions` | List sessions. Requires the operator token. |
| `GET` | `/api/v1/agent-sessions/{session_id}` | Read effective lease state. Requires the operator token. |
| `POST` | `/api/v1/agent-sessions/{session_id}/approve` | Human UI approval with `expected_version`; configured AI is separately selectable. Requires the operator token. |
| `POST` | `/api/v1/agent-sessions/{session_id}/heartbeat` | Renew the process lease using its in-memory bearer secret. |
| `POST` | `/api/v1/agent-sessions/{session_id}/revoke` | Human revoke; terminal and operator-token protected. |
| `POST` | `/api/v1/agent-sessions/{session_id}/exit` | Mark process exit using its in-memory bearer secret. |
| `GET` | `/api/v1/agent-sessions/{session_id}/actions` | Read paginated redacted audit events. Requires the operator token. |

The normal `tasksignal mcp` runtime performs this lifecycle locally. A raw
session secret exists only in that process; the database stores its namespaced
hash. Heartbeats run every 30 seconds against a 60-second lease. Approval ends on
revoke, expiry, or process exit.

Audit events are append-only and expose safe request/result summaries, status,
capability, target, correlation/operation IDs, and safe error codes. They do not
expose session secrets, idempotency keys, credentials, local notes, raw source
payloads, or raw identities.

## MCP Surface

`tasksignal mcp` exposes stdio MCP from the optional `mcp` extra.

Read tools:

- `list_projects`
- `list_project_runs`
- `compare_project_runs`
- `search_opportunities`
- `get_opportunity_thread`
- `get_evaluation`
- `get_build_packet`
- `verify_build_packet`

Write tools:

- `create_project`
- `update_project`
- `run_project`
- `set_opportunity_decision`
- `append_evidence_label`
- `create_build_packet`

Every write requires the approved process session, an idempotency key, and an
expected version. Configured-AI packet generation additionally requires the
`use_configured_ai` capability. Conflicts and replays return structured results.

Resources:

- `tasksignal://projects/{project_id}/runs/{run_id}/delta`
- `tasksignal://opportunity-threads/{thread_id}`
- `tasksignal://build-packets/{packet_id}/artifacts/{artifact_name}`

MCP does not expose deletion/reset, source-host authorization, credentials,
retention changes, arbitrary URL fetching, shell/filesystem operations, direct
GitHub writes, HTTP transport, or OAuth.
