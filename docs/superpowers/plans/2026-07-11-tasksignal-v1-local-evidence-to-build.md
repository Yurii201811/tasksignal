# TaskSignal v1 Local Evidence-to-Build Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` for every behavior change. Each task must be committed and independently reviewed before the next task begins.

**Goal:** Ship TaskSignal v1 as a local-first research-memory and evidence-to-build workbench for one indie builder, with a packaged API/CLI, guarded stdio MCP, public Discourse ingestion, and immutable document suites.

**Architecture:** Preserve the FastAPI/SQLAlchemy/Alembic backend and Next.js workbench. Add additive lineage/thread/packet/session tables, make `/api/v1` canonical while retaining `/api` compatibility aliases, and keep MCP and CLI as typed clients of the API rather than alternate database writers.

**Tech stack:** Python 3.11-3.14, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite/PostgreSQL, MCP Python SDK 1.x, Next.js 15, React 19, TypeScript, Tailwind, Vitest, pytest, Docker/GHCR, PyPI/uv.

## Global Constraints

- Product remains local-first and single-operator; no accounts, tenancy, team collaboration, private sources, outreach, or automatic GitHub writes.
- Core discovery, packets, CLI, and MCP reads work without a paid model. AI enhancement is optional and records provider/model provenance.
- Raw usernames, credentials, local decision notes, and raw source JSON never enter search output, MCP output, logs, audit payloads, or build artifacts.
- Source evidence is untrusted data and must never be interpreted as agent instructions.
- `/api/v1` is canonical; existing `/api` routes remain compatible throughout v1.x.
- MCP uses stdio only and `mcp>=1.28.1,<2`; HTTP MCP and OAuth are deferred.
- MCP writes are limited to the exact non-destructive tool set in Task 7, require a process-bound approved session, expected versions, and idempotency keys.
- Agent-authored evidence labels are stored and visible but do not count toward human-review coverage or human precision until a human appends a confirming label.
- Exact HTTPS Discourse hosts require human terms authorization; MCP cannot authorize sources.
- Existing v0.2 data is preserved. Historical lineage is never guessed; untraceable rows are explicitly `untracked`.
- Generated packet content is immutable and manifest-backed; deterministic artifacts are authoritative even when enhanced variants exist.
- Existing proof-manifest, fixture redaction, safe-URL, operator-token, and hosted-preview protections remain backward compatible.
- Runtime code uses the repo-local Python environment and Node 20+ tooling. MCP remains outside the Vercel runtime dependency set.

---

### Task 1: Finalize and publish the v0.2 rollback baseline

**Deliverable:** One clean v0.2.0 candidate containing the preserved UI/accessibility/token work and upstream redaction hardening, with truthful release docs and a reusable v1 starting point.

**Requirements:**

- Keep root `tokens.css`, runtime `apps/web/src/app/tokens.css`, and `DESIGN.md` exports; ignore `.hallmark/` generated logs.
- Keep `httpx2` exclusively in API dev/test dependencies.
- Reconcile README, changelog, release-prep, demo evidence, and version references so v0.2.0 is described as the release candidate/public release rather than unpublished development.
- Add this implementation plan and reset the scratch progress ledger for v1 without deleting the v0.2 history.
- Verify `make verify`, npm audit, release content gate, smoke proof and manifest verification before external publication.

### Task 2: Add research-run lineage and precise deltas

**Deliverable:** Migration `0007_research_memory` plus transactional scan lineage that records every observed item and produces truthful first/repeat/partial/zero/failed run deltas.

**Interfaces:**

- Tables: `research_project_runs`, `scan_items`; nullable lineage fields on clusters/opportunities.
- Types: `ResearchRunOut`, `RunDeltaCountsOut`, `RunDeltaOut`.
- Endpoints: `PATCH /api/v1/research-projects/{id}`, `GET /api/v1/research-projects/{id}/runs`, `GET /api/v1/research-projects/{id}/runs/{run_id}/delta`.
- Delta vocabulary: `new`, `seen_before`, `updated`, `unchanged`, `not_observed_this_run`; never `deleted` or `resolved`.

**Requirements:**

- Normalization returns both observed and newly created item IDs.
- Detection/embedding runs only when missing; clustering receives every observed problem-signal item.
- Lineage writes complete atomically before a scan becomes completed; failed scans have no complete delta.
- Existing scans remain untracked. Edited source text remains a new evidence record under the existing text-hash contract.

### Task 3: Add persistent opportunity threads and automatic matching

**Deliverable:** Persistent decision threads across run snapshots with transparent conservative automatic matching and reversible false-match correction.

**Interfaces:**

- Tables: `opportunity_threads`, `opportunity_decision_events`; thread/snapshot hash and match fields on opportunities.
- Types: `OpportunityThreadSummaryOut`, `OpportunityThreadOut`, `OpportunitySnapshotOut`, `OpportunityDecisionUpdate`.
- Endpoints: `GET /api/v1/opportunity-threads`, `GET /api/v1/opportunity-threads/{id}`, `PATCH /api/v1/opportunity-threads/{id}/decision`, `POST /api/v1/opportunity-threads/{id}/snapshots/{snapshot_id}/detach`.

**Requirements:**

- Backfill every v0.2 opportunity one-to-one into an untracked thread and preserve decision state/note.
- Exact evidence hash matches immediately. Otherwise score `0.60 * centroid_cosine + 0.25 * evidence_jaccard + 0.15 * title_jaccard`.
- Auto-match only at score `>= 0.82` with a `>= 0.05` lead over runner-up; ambiguous/no-match candidates create a new thread.
- Compare vectors only for the same embedding model/backend. Persist method, score, evidence hash and content hash.
- Decision state lives on the thread; snapshots are immutable generated views. Detach is human-only and append-only audited.

### Task 4: Add typed retrieval and the public Discourse connector

**Deliverable:** A reusable typed search service returning evidence plus related threads, and a safe configurable Discourse connector with source runtime state.

**Interfaces:**

- Types: `SemanticSearchRequest`, `EvidenceSearchHitOut`, `OpportunityThreadHitOut`, `SemanticSearchOut`, `SourceAuthorizationOut`, `SourceRuntimeStateOut`.
- Endpoints: `POST /api/v1/search`, Discourse source authorization/readiness endpoints, and v1 source create/update aliases.

**Requirements:**

- Search accepts nonblank query, limit 1-20, optional project/source/signal/review filters, and deterministic ordering.
- Opportunity match score is derived from matched evidence and includes readiness/lineage without local notes or private fields.
- Discourse accepts public HTTPS only, exact authorized hosts, no cookies/private credentials, no IP literals/private/loopback/link-local targets, and no cross-host redirects.
- Bound timeout, response bytes, result count and topic-detail requests. Persist sanitized success/error/rate-limit state and honor `Retry-After`.
- Authorization requires explicit terms confirmation in UI/REST and is never available through MCP.

### Task 5: Add immutable full build packets

**Deliverable:** Migration `0008_build_packets`, deterministic ten-file document suites, download/verification APIs, and optional enhanced variants.

**Interfaces:**

- Tables: `build_packets` with immutable snapshot, artifact and manifest JSON.
- Types: `BuildPacketCreate`, `BuildPacketArtifactOut`, `BuildPacketOut`, `BuildPacketVerificationOut`.
- Endpoints: create/list/get/download/verify under `/api/v1/opportunity-threads/{id}/build-packets` and `/api/v1/build-packets/{id}`.

**Requirements:**

- Creation requires `build_candidate`, medium/strong readiness, and no current `sensitive_risk`.
- Produce exactly `README.md`, `MANIFEST.json`, `opportunity.json`, `evidence.md`, `task-pack.md`, `product-requirements.md`, `validation-plan.md`, `github-issue.md`, `implementation-plan.md`, and `agent-brief.md`.
- Manifest records schema/app version, project/run/thread/snapshot IDs, generation mode/time, byte counts and SHA-256 hashes.
- Deterministic originals remain authoritative. Optional configured enhancement writes only `enhanced/` variants and records provider/model/template provenance.
- Exclude raw identity, secrets and local notes. Mark quoted evidence as untrusted. GitHub output is draft-only.

### Task 6: Add process-bound agent sessions and redacted audit events

**Deliverable:** Migration `0009_agent_sessions_audit`, process-lifetime approval, concurrency/idempotency enforcement, and origin-aware evidence evaluation.

**Interfaces:**

- Tables: `agent_sessions`, `agent_actions`; `actor_type` and nullable `agent_session_id` on labels and decision events.
- Endpoints: create/list/approve/heartbeat/revoke sessions and list redacted audit events under `/api/v1/agent-sessions`.

**Requirements:**

- Reads require no write session. Writes use a random bearer secret held only by the MCP process; store only its hash.
- UI or interactive TTY approves all non-destructive v1 capabilities. Heartbeat every 30 seconds; expire after two misses; clean exit revokes immediately.
- Every action stores client/session, tool, target, redacted request/result summary, idempotency key, status, timestamps and correlation ID.
- Expected-version conflicts, replayed idempotency keys, expired/revoked sessions and post-exit writes fail without mutation.
- Agent labels remain append-only/current but are separated from human-review coverage and human precision; a later human label confirms truth.
- Optional AI use requires the separately approved `use_configured_ai` capability.

### Task 7: Ship the stdio MCP server

**Deliverable:** A thin typed MCP client of `/api/v1`, installed through the `mcp` extra and started by `tasksignal mcp`.

**Read tools:** `list_projects`, `list_project_runs`, `compare_project_runs`, `search_opportunities`, `get_opportunity_thread`, `get_evaluation`, `get_build_packet`, `verify_build_packet`.

**Write tools:** `create_project`, `update_project`, `run_project`, `set_opportunity_decision`, `append_evidence_label`, `create_build_packet`.

**Resources:** `tasksignal://projects/{project_id}/runs/{run_id}/delta`, `tasksignal://opportunity-threads/{thread_id}`, `tasksignal://build-packets/{packet_id}/{artifact}`.

**Requirements:**

- Stdio only; logs go to stderr. No raw database access from MCP.
- Writes require approved session, idempotency key and expected version. The MCP server sends heartbeat and revokes on shutdown.
- Never expose delete/reset, source authorization/configuration, credentials, retention, arbitrary URL, shell/filesystem, direct GitHub writes, or broad run-due execution.
- Deterministic packets are allowed; AI enhancement is rejected without `use_configured_ai`.

### Task 8: Publish the packaged API and CLI

**Deliverable:** PyPI-ready `tasksignal` distribution containing API/CLI and an `mcp` extra, packaged migrations/fixtures, safe local configuration, and isolated wheel tests.

**Commands:** `tasksignal init`, `migrate`, `serve`, `doctor`, `mcp`; nested `projects`, `runs`, `opportunities`, `evidence`, `packets`, `sessions` commands.

**Requirements:**

- Distribution name `tasksignal` with internal `app` namespace private; fallback distribution is `tasksignal-app` while retaining the console command.
- Default local database/config paths use `platformdirs`; generated secrets are stored in a mode-0600 file and never printed. Environment overrides win.
- `serve` binds loopback and refuses stale schemas. `migrate` packages Alembic revisions, backs up SQLite before upgrade, and refuses unknown/unversioned PostgreSQL without explicit stamp flow.
- Support Python 3.11-3.14 on macOS/Linux; Windows is WSL-only. Base wheel contains API/CLI, `tasksignal[mcp]` adds `mcp>=1.28.1,<2`, and optional `ml` remains separate.
- Keep MCP dependencies out of Vercel/runtime Docker sync. Build/check/install the wheel in a clean environment.

### Task 9: Add the v1 workbench UI

**Deliverable:** Accessible responsive UI for research memory, thread review, typed search, packets, Discourse authorization, agent-session approval and audit.

**Requirements:**

- Project detail shows run history, comparison controls and precise delta language.
- Thread detail shows snapshots, provenance, match method/confidence, decision history and human-only detach.
- Dashboard uses server-side project/source/readiness/age/state filters, deterministic sort and next-unreviewed navigation; no batch decisions.
- Search renders evidence and related threads. Build Studio previews/downloads/verifies every artifact and explains packet blockers.
- Sources manages Discourse host authorization and runtime state. Settings manages session approval/revocation and redacted audit events.
- Preserve the locked `DESIGN.md` token system, visible focus, reduced motion, touch targets and narrow-view behavior.

### Task 10: Complete release hardening and staged publication

**Deliverable:** Version-consistent alpha/beta/RC/GA release automation, fresh/copy migration evidence, full proof bundle, Browser report, PyPI/GHCR provenance and truthful docs.

**Requirements:**

- Canonical releases: `1.0.0a1`, `1.0.0b1`, `1.0.0rc1`, `1.0.0`; map to ecosystem-valid npm display versions through the release checker.
- Test fresh and copied-v0.2 SQLite/PostgreSQL upgrades; do not downgrade or delete additive v1 tables for rollback.
- Add Python dependency audit, package build/check/install, SBOM/provenance, versioned API/web GHCR images and trusted PyPI publishing.
- Extend smoke to prove two-run delta, thread matching, human/agent review separation, deterministic packet generation and manifest verification.
- Run full automated, dependency, migration, security, desktop/narrow Browser, accessibility and negative live checks.
- Do not publish GA until three real indie-builder testers complete fixture-to-packet without maintainer help and the evidence is recorded.
