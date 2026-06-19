# Next-Version Roadmap

## Recommended Product Direction

Do not turn TaskSignal into a generic AI dashboard. The next version should make the current evidence-backed research loop more trustworthy, repeatable, and decision-oriented.

Recommended next-version theme:

> TaskSignal v0.2: Evidence Quality And Research Decisions

## v0.2 Scope: 2-4 Week Improvement Slice

### 1. Fix Operator-Token UX For Prompt Enhancement

Why now:

- The API gate is correct, but the UI action is not wired to pass the token.

Acceptance criteria:

- Enhancement button is disabled or explained when runtime/token is unavailable.
- When token exists, request includes `X-Operator-Scan-Token`.
- Frontend test covers header behavior.
- API failure copy is user-actionable.

### 2. Dependency Advisory Cleanup

Why now:

- Current `npm audit` reports one high and one moderate advisory.

Acceptance criteria:

- Lockfile updated through controlled dependency bump.
- `npm audit --audit-level=moderate` passes or documented accepted risk remains.
- `make verify` passes after update.

### 3. Evidence Review States

Why now:

- Users need to decide what to do with opportunities, not just view them.

Suggested states:

- New
- Needs more evidence
- Promising
- Rejected
- Duplicate
- Build candidate

Acceptance criteria:

- Opportunity detail can save review state and note.
- Dashboard/projects show counts by state.
- Exports include review state when present.

### 4. Evaluation Labels And Quality Report

Why now:

- The detector is heuristic; labels turn this into an auditable learning loop.

Acceptance criteria:

- Users can label evidence as true signal, false positive, unclear, or duplicate.
- Add evaluation report with precision/recall on labeled examples.
- Add fixture/evaluation test for report generation.

### 5. Semantic Search To Opportunity Bridge

Why now:

- Search currently returns items but not opportunities.

Acceptance criteria:

- Search results include related opportunities or the API contract removes `opportunities`.
- Users can jump from an evidence hit to source opportunity/cluster.
- Search can filter by source and signal type.

### 6. Scan Comparison And Delta View

Why now:

- Saved projects need memory across runs.

Acceptance criteria:

- Project detail shows latest runs and changes since previous run.
- New signals/opportunities are highlighted.
- Zero-opportunity runs explain what changed.

### 7. Source And Runtime Readiness Hardening

Why now:

- TaskSignal already has good readiness APIs; v0.2 can make them more actionable.

Acceptance criteria:

- Warn when `AUTHOR_HASH_SALT` is default.
- Clarify source enabled semantics.
- Show credentialed connector readiness without exposing secrets.
- Add tests for readiness warnings.

## v0.3 Scope: Hosted-Ready Or Agent-Ready Branch

Choose one strategic branch before building v0.3.

### Option A: Hosted-Ready Research Workbench

Build this only if the goal is remote/team use.

Required:

- authentication
- per-workspace data isolation
- token vault or server-side secret handling
- retention and deletion controls
- background job queue
- rate-limit state and retry policy
- audit logs
- admin deletion endpoint
- hosted deployment runbook

### Option B: Local Agent Handoff Power Tool

Build this if the goal is better Codex/agent workflows without SaaS complexity.

Required:

- richer task-pack variants
- MCP server for querying opportunities
- local project export bundles
- PRD/issue/implementation-plan generators
- prompt-injection checks for evidence text
- reviewed opportunity state machine
- local-only evaluation dashboard

Recommendation:

- Pick Option B first. It fits the current local-first architecture and makes the product more distinctive without introducing SaaS security burden.

## Top 10 Improvement Ideas For GPT 5.5 Pro To Expand

1. Opportunity review states and decision log.
2. Labeled evaluation and model-quality report.
3. Token/runtime-aware prompt enhancement UX.
4. Semantic search with opportunity/cluster results.
5. Scan comparison for saved projects.
6. Dependency advisory cleanup and automated audit gate.
7. Source diversity and evidence quality score.
8. Readiness warnings for default author hash salt and hosted-risk config.
9. Export variants: PRD, GitHub issue, validation plan, implementation plan.
10. Local MCP/query interface for Codex and other agents.

## What Not To Prioritize Yet

- Multi-tenant accounts before hosted security design.
- Paid LLM dependency for core workflow.
- Outreach automation.
- Private community scraping.
- Generic vanity metrics.
- Large model claims without evaluation.
- Rewriting the UI away from the current research-grade tone.
