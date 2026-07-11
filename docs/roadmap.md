# Roadmap

TaskSignal prioritizes a trustworthy local evidence-to-build loop over opaque
automation. `v0.2.0` is the published rollback baseline. The v1 workbench is
implemented in source but remains pre-GA until migration, release, and independent
usability evidence is complete.

## Implemented v1 Workbench

- Immutable research-project runs with source/query/limit snapshots and every
  observed item, including previously stored evidence.
- Precise evidence, signal, and opportunity deltas using `new`, `seen before`,
  `updated`, `unchanged`, and `not observed this run`.
- Project-scoped opportunity threads with evidence/content hashes, deterministic
  match thresholds, compatible-embedding checks, confidence/margin details,
  append-only decisions, and human detach correction.
- One typed redacted semantic search service shared by REST, CLI, and MCP.
- Explicitly authorized public Discourse origins with terms confirmation,
  same-origin HTTPS enforcement, SSRF controls, bounded responses, and visible
  retry/failure state.
- Immutable ten-file deterministic build packets with manifest, hashes, lineage,
  integrity verification, and optional additive AI variants.
- Process-bound stdio MCP with immediate reads, approved non-destructive writes,
  separate configured-AI capability, idempotency, optimistic concurrency,
  heartbeat expiry, and redacted append-only audit.
- Installable `tasksignal` API/CLI distribution with packaged fixtures and
  migrations, private local initialization, schema-checked serving, and guarded
  SQLite upgrades.
- Next.js operator surfaces for run history/deltas, opportunity threads, Build
  Studio, Discourse readiness, agent sessions, and redacted audit.

Implemented does not mean generally available. PyPI publication, public
container provenance, completed cross-platform CI evidence, migration rehearsal,
and independent user completion are separate release gates.

## v1 Release Readiness

- Rehearse clean and copied-v0.2 upgrades on SQLite and PostgreSQL, including
  backup restoration and explicit handling of unversioned schemas.
- Complete the configured Python 3.11–3.14 wheel matrix on both Linux and macOS
  in live CI; document WSL-only Windows support.
- Run full `make verify`, `make smoke`, `make package-check`, manifest checks,
  npm audit, Python base/MCP dependency audit, release check, desktop/narrow
  browser flows, and accessibility checks against one candidate SHA.
- Assess the optional `ml` extra separately. Its sentence-transformers,
  scikit-learn, and transitive dependencies are outside the base+MCP audited
  release surface.
- Verify deterministic packet reproducibility, tamper rejection, privacy
  exclusions, prompt-injection-shaped evidence, and configured-AI fallback.
- Verify MCP approval, expiry, revoke, replay, idempotency, conflicts, audit
  redaction, process exit, and real stdio protocol behavior.
- Complete independent evidence-to-build usability sessions with three indie
  builders. Do not claim this result before the sessions and artifacts exist.
- Reserve or select the final Python distribution name at publication time; keep
  the `tasksignal` command stable if the distribution name must change.
- Publish GitHub, Python, and versioned container artifacts only when they are
  pinned to the same SHA with a CI run, proof manifest, and migration record.

## Maintainer Workflow

- Keep public releases tied to an exact changelog version, clean release check,
  dependency evidence, built-artifact inspection, and immutable proof manifest.
- Review dependency changes with test output and a concise risk note.
- Require human review before enabling a new source host, changing stored public
  fields, or expanding an agent capability.
- Keep REST, CLI, MCP, UI, build-packet schema, and the
  `skills/tasksignal-opportunity-builder` handoff aligned.
- Preserve `v0.2.0` as the documented rollback point until v1 migration evidence
  is accepted.

## Security and Privacy

- Keep connector credentials out of source records, responses, packet artifacts,
  audits, and screenshots.
- Preserve author minimization and human/agent evidence-label separation.
- Treat all source excerpts and model output as untrusted data.
- Keep Discourse authorization exact-origin, human-controlled, and unavailable
  through MCP.
- Keep configured-AI generation separately approved because it can incur cost.
- Maintain deterministic packet originals and verification as the authority even
  when enhanced variants exist.
- Do not turn the shared operator token into a claim of multi-user authentication.

## Deferred Beyond v1

- Accounts, tenancy, team collaboration, and production hosted readiness.
- Private sources, outreach, messaging, and automatic GitHub issue creation.
- Deletion/reset through MCP, HTTP MCP, and OAuth.
- Background job infrastructure and hidden in-process scheduling.
- pgvector approximate-nearest-neighbor production search.
- Third-party connector plugins.
- Native Windows support outside WSL.
