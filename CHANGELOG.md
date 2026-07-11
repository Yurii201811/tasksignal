# Changelog

All notable public-facing changes to TaskSignal are recorded here.

## Unreleased

## 1.0.0a1 - 2026-07-11

### Added

- Immutable research runs, precise run deltas, persistent opportunity threads,
  confidence-gated matching, decision history, and human-only snapshot detach.
- Typed semantic search across safe evidence excerpts and related threads, plus
  an allowlisted public Discourse connector with explicit per-host terms approval.
- Reproducible, hash-verifiable ten-file build packets with authoritative
  deterministic originals and optional provenance-recorded AI variants.
- Process-bound Agent Sessions, append-only redacted action audit, and a guarded
  stdio MCP server with eight read tools, six non-destructive write tools, and
  `tasksignal://` resources.
- The installable `tasksignal` Python distribution, safe local init/migrations,
  noun-first CLI, packaged fixtures/revisions, and an optional `mcp` extra.
- Workbench UI for run history, thread review, Build Studio, Discourse source
  authorization, Agent Sessions, and action audit on desktop and narrow screens.

### Changed

- `/api/v1` is canonical; the existing `/api` surface remains a v1.x
  compatibility alias.
- Scans embed only missing evidence while clustering every signal-bearing item
  observed in the immutable run snapshot.
- Python packaging supports 3.11 through 3.14 on macOS and Linux; Windows is a
  WSL-only target for v1. The Next.js UI remains source/container distributed.

### Security

- Discourse requests reject IP literals, private/link-local destinations,
  cross-host redirects, oversized responses, and unapproved exact origins.
- MCP writes require process approval, heartbeat leases, idempotency keys, and
  optimistic versions; configured-AI generation requires separate capability.
- Packaged migrations fail closed for unknown or nonempty unversioned schemas,
  fingerprint non-table objects, and back up stale SQLite databases before upgrade.
- Release publication requires exact-SHA evidence, canonical on-main tags,
  phase-specific RC/GA usability records, immutable digest promotion, exact-hash
  recovery, least-privilege OIDC jobs, pinned actions, and verified draft assets.
- Base and MCP dependency audits pass. The separately assessed optional ML
  stack currently reports `torch 2.12.0` / `CVE-2025-3000` without a fixed
  version, so it is not part of the alpha's release-supported surface.

### Release status

- This is the first v1 alpha candidate. A local PostgreSQL 16 + pgvector
  fresh/copied-v0.2/fail-closed rehearsal passes. PyPI/GHCR publication,
  cross-platform Actions proof, and three independent builder sessions remain
  unrecorded; GA remains blocked.

## 0.2.0 - 2026-07-11

### Added

- Persistent opportunity decision states and export-excluded local review notes.
- Append-only evidence reviews, transparent evidence readiness, and a selection-biased evaluation report.
- Decision queue filtering, opportunity review controls, and the Evaluation page.
- Decision Context in evidence bundles and Codex task packs.
- A responsive application shell, visible focus treatment, reduced-motion support,
  and shared design-token exports for the repository and runtime web app.
- First-run smoke checks can now write a shareable Markdown proof report with
  fixture counts, task-pack evidence, dashboard checks, and runtime boundaries.
- Evidence bundle Markdown export for opportunity detail pages and
  `/api/opportunities/{id}/evidence.md`.
- Local `make doctor` setup checks for fresh clones and contributor onboarding.
- Source limits and terms guidance for live connectors, hosted demos, and
  rate-limit review.
- Scan detail pages and outcome telemetry for reviewing ingestion results and
  distinguishing working connectors from weak source/query fit.

### Changed

- Local API/web/database host ports bind to loopback by default.
- Development setup uses locked API and web dependencies through `make setup`.
- First-run smoke evidence now proves the complete decision and evidence-review loop.
- Starlette TestClient verification uses `httpx2` only through the API dev/test
  dependency set; production connector dependencies are unchanged.

### Security

- Local review notes remain outside shared exports, and unauthenticated review writes are documented as local-only.
- Compatible frontend dependency advisories were resolved without a framework major upgrade.
- Secret redaction is hardened for connector failures before error details reach
  API responses or persisted scan records.

### Fixed

- Fixture demo processing is non-destructive by default, and destructive resets require `DEMO_RESET_TOKEN`.
- Public scan source exposure defaults to `fixture,hackernews` through `PUBLIC_SCAN_SOURCES` so unauthenticated callers cannot spend server-side connector credentials.
- Public scan readiness now warns when `PUBLIC_SCAN_SOURCES` excludes every browser-safe source, and failed scan requests report `Allowed public scan sources: none` instead of an empty allowlist.
- Source registry writes now require an operator token, reject secret-like `config_json` keys, and return redacted config on readback.
- Prompt enhancement now requires an operator token before any configured OpenAI or Ollama request is made.
- Security reporting docs now include a no-details public fallback when GitHub private vulnerability reporting is unavailable.
- Source URLs are limited to absolute `http` and `https` links before storage and before frontend rendering.
- API, web, lockfile, and release-documentation version references now identify
  the `v0.2.0` release candidate.

## 0.1.3 - 2026-06-01

Evidence and screenshot polish.

### Added

- Connector guidance in the dashboard so live-source scans show credential, query, and privacy expectations before running.
- Evidence trail and export-readiness UI for opportunity detail and generated prompt review.
- Prompt generation now includes source mix, evidence focus terms, traceability checks, and current TaskSignal endpoints/schema.

### Fixed

- Live scan failures now return redacted, connector-specific guidance without leaking credential values.
- README dashboard screenshot now reflects the current production UI and fixture demo data.
- API and model-card docs now match the default thematic clustering path and current scan endpoint behavior.

## 0.1.2 - 2026-06-01

OSS review-readiness polish.

### Added

- Demo evidence snapshot with fixture counts, source mix, top generated opportunities, and reproduction commands.
- Release-readiness GitHub Action so the public repository shows the release gate in CI.
- Repository readiness notes that call out the remaining public-signal gap honestly.

### Fixed

- Default live scan now uses a no-credential GitHub Issues query that is more likely to produce actionable signals than the broad Ask HN feed.
- Live scans can create reviewable opportunities from smaller related signal sets, which makes first-run public-source checks more useful.
- Prompt generation now redacts or skips known author identifiers when building exported evidence excerpts and common phrases.
- Added regression coverage to keep raw author identifiers out of generated prompt exports.

## 0.1.1 - 2026-05-31

Application-readiness polish.

### Added

- Browser-verified dashboard screenshot in the README.
- Release-readiness check for docs, tracked generated files, obvious secret patterns, and clean release state.
- Codex for OSS application evidence note with honest claims, API-credit workflow, and remaining external-signal gaps.

### Fixed

- Regeneration endpoint now rebuilds opportunity fields and prompts from stored cluster evidence instead of reusing previously generated text.
- FastAPI startup table creation now uses the lifespan hook instead of the deprecated startup-event hook.

## 0.1.0 - 2026-05-31

Initial public release candidate.

### Added

- Local-first demo pipeline for turning public discussion fixtures into scored opportunity cards.
- FastAPI backend, Next.js dashboard, Docker Compose setup, Makefile, and GitHub Actions CI.
- Privacy-conscious normalization that stores author hashes by default.
- Deterministic fallback embeddings so the demo works without paid LLM APIs or model downloads.
- Opportunity scoring, evidence spans, Markdown prompt export, and public documentation.
- Security policy, contributing guide, data ethics notes, model card, and release-readiness notes.
- Live-source scan workflow for supported public APIs, with credential-gated connectors where required.

### Notes

- TaskSignal is an application repository, not a published package. Run it from source or Docker Compose.
- The project is pre-1.0 and should not be used for automated outreach, profiling, or private-data collection.
