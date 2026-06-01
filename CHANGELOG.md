# Changelog

All notable public-facing changes to TaskSignal are recorded here.

## Unreleased

### Added

- Source limits and terms guide for live connectors, hosted demos, and rate-limit review.

### Fixed

- Fixture demo processing is non-destructive by default, and destructive resets require `DEMO_RESET_TOKEN`.
- Public scan source exposure defaults to `fixture,hackernews` through `PUBLIC_SCAN_SOURCES` so unauthenticated callers cannot spend server-side connector credentials.
- Source URLs are limited to absolute `http` and `https` links before storage and before frontend rendering.

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
