# Changelog

All notable public-facing changes to TaskSignal are recorded here.

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
