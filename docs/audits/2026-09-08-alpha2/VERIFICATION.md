# TaskSignal alpha 2 verification

Date: 2026-09-08 (Europe/Stockholm).

Implementation branch: `codex/tasksignal-next-version`.
Base: `eb11c5821754d52d68536882b4870cabe943cd85`.
Worktree: `/Users/yuriibakurov/Documents/Github Project/tasksignal/.worktrees/tasksignal-next-improvement`.
Version: API `1.0.0a2`; web `1.0.0-alpha.2`.

## Changed

- Replaced the static home with real workspace totals, next-review navigation,
  recent projects, and credential-free fixture processing.
- Added a contextual shell, keyboard quick navigation, consistent page hierarchy,
  missing-page recovery, and a retryable page-error boundary.
- Promoted the decision queue in visual and document order; added local text
  search, sorting, and progressive disclosure without replacing API scope filters.
- Added URL-backed evidence search, same-route query handoff, browser history,
  race protection, preserved results during refresh, and copy-link support.
- Fixed scheduling intervals, historical generation targets, and detachment of
  snapshots referenced by immutable build packets.
- Refreshed vulnerable web dependencies within the existing direct major ranges,
  and upgraded transitive cryptography to 50.0.1 without changing API constraints.

## Verified

- Backend pytest: **535 passed**, isolated temporary SQLite database.
- Web Vitest: **88 passed**, 19 test files.
- ESLint and Ruff: passed. Fixture redaction check: passed.
- Production Next.js build: passed, including type checking and 14 static pages.
- Clean `npm ci`: passed; `npm audit`: **0 vulnerabilities**.
- Hashed Python production + MCP audit: **no known vulnerabilities**.
- Repository release metadata/doc/secret-pattern checks: passed for `1.0.0a2`.
- First-run smoke: passed; final saved [proof bundle](proof/README.md) manifest
  verified after all dependency updates.
- Fixture smoke: 18 raw items, 17 signals, 5 opportunities; identical rerun
  preserves 5 threads with no false new threads. Human/agent evidence labels
  remain separate. The immutable build packet contains 10 verified files.

Browser verification used the in-app browser against a production Next server
and a loopback API with a separate fixture-only SQLite database. Checked desktop
home and dashboard, the 390px mobile home/queue, live demo completion, command
navigation, same-route evidence-search query changes, browser Back, and 404
recovery. Mobile document width remained within the viewport. The final browser
console inspection had no errors. These are focused checks, not a claim of full
accessibility conformance.

Independent integration review identified and closed: dashboard visual/DOM
order mismatch, search query changes on an already-mounted route, duplicate
loading indicators, and premature project empty-state content. Stale EvidenceItem
test fixtures were updated to the current API shape.

## Runtime and boundaries

- Web runtime: `/opt/homebrew/opt/node@20/bin/node` (20.20.0).
  The host's Node 22 binary has a missing dynamic library and was not used.
- Python: repository `apps/api/.venv`, Python 3.12.
- Preview: `http://127.0.0.1:3000`; API: `http://127.0.0.1:8000`.
- Preview database: `/tmp/tasksignal-next-version-preview.db`, fixture data only.
- Older root and decision-workbench edits were preserved. No original workspace
  database was changed. No push, release tag, publication, or deployment occurred.
- PostgreSQL/Docker, remote CI, cross-platform packaging, optional ML dependencies,
  and independent usability sessions were not rerun for this local alpha update.

Resume from this branch/worktree. Use `make test`, `make lint`, and
`make release-check` for the broader release gate before considering publication.
