# TaskSignal alpha 3 verification checkpoint

Date: 2026-09-16 (Europe/Stockholm).
Branch: `codex/tasksignal-next-version`.
Base: `d9d55223246fcb933c3884a7781ed2107aa781ef`.
Worktree: `/Users/yuriibakurov/Documents/Github Project/tasksignal/.worktrees/tasksignal-next-improvement`.
Version: Python `1.0.0a3`; web `1.0.0-alpha.3`.

## Latest follow-up: 2026-09-22

Fable's full follow-up is committed as `7a8c736` (26 files, 123 web tests).
The subsequent review found that run history treated failed HTTP-200 scan
responses as successful runs. This is now fixed, with four regression cases,
**127 passing web tests**, browser checks of failed/completed responses,
TypeScript, ESLint, and a production build. See
[`../2026-09-22-run-status-fix.md`](../2026-09-22-run-status-fix.md).

The user requested committing all task changes and pushing the current feature
branch on 2026-09-22. This is branch publication, not a public release or
deployment. The final Impeccable/design-documenter review remains unperformed.

## Scope

The user's priority is to find and review buildable ideas faster. This update
keeps the established teal design and backend contracts, and changes the home,
decision queue, opportunity review, and project browsing workflows. It does not
claim measured speed gains or change build-packet eligibility.

- Shareable queue filters and sorting, preserved detail return paths, and
  continuous next-item navigation.
- Responsive opportunity rows with visible risk and readiness, and secondary
  evidence gaps and scoring under disclosure.
- Populated home focused on current work; empty-only onboarding.
- Browse-first projects, local search/status filters, and recoverable data states.
- Review invalidation across snapshots, threads, evaluation, and readiness;
  project-run invalidation includes project history and comparison caches.
- Unsaved-draft warnings for page links/reload; Next disabled while dirty;
  in-progress notes survive background response updates. Browser Back/Forward
  is not intercepted and should follow a saved review.

## Original checkpoint verification (before Fable's full follow-up)

- Backend: **535 tests passed**, repository Python 3.12, isolated temporary DB.
- Web: **106 tests passed**, 22 files, Node 20.20.0, Vitest 4.1.11.
- TypeScript, ESLint, Ruff, fixture redaction, and `git diff --check`: passed.
- Impeccable static detector: **0 findings** across all changed TSX/CSS targets;
  recorded once in `DETECTOR.json`. Do not rerun it during the remaining visual
  review; pass this report to the reviewer.
- Repository release metadata, documentation, tracked-file secret-pattern scan,
  and changelog checks: passed for 1.0.0a3 (without a clean-tree requirement or
  remote CI URL).
- Production Next.js build: passed; 14 static pages generated. This build
  preceded the Vitest-only security patch; runtime dependencies did not change.
- `npm audit --audit-level=moderate`: **0 vulnerabilities** after updating
  Vitest/mocker to 4.1.11. Advisory:
  <https://github.com/advisories/GHSA-82fw-gwwq-j7x9>.
- Hashed production + MCP Python audit: **no known vulnerabilities**.
- Python wheel and sdist built and passed Twine checks. Built-wheel smoke:
  **passed on Python 3.11.5**, version 1.0.0a3.
- `make smoke`: passed. Fixture flow: 18 raw items, 17 signals, 5 opportunities;
  identical rerun preserved threads; actor-aware reviews remained distinct;
  ten-file immutable build packet verified with 14 private markers excluded.

## Browser checks and pending finish

The in-app Browser ran against a loopback API using
`/tmp/tasksignal-alpha3-preview-20260916.db`; original workspace data was not used.
The first visual pass covered desktop home/queue and narrow mobile home/review.
Mobile queue whitespace was tightened after that pass.

Verified through the real UI: demo completion; fixture project creation and
run; project status/cache refresh; queue project/decision/search/sort filtering;
copy-link success; bookmarked view survives reload; dirty review disables Next.

**Closed on 2026-09-16 (later session):** the unsaved-navigation warning,
save-and-next readback, next/back context, project rerun and cache refresh,
thread save, packet generation and verification, production-preview reload,
320/768px overflow measurements, and console check were completed against a
new disposable database. Results, the one concrete fix they produced (the
opportunity score card at 320px), and the remaining deferred items are recorded
in [`IMPLEMENTATION-LEDGER.md`](IMPLEMENTATION-LEDGER.md). Existing
`.impeccable/review/alpha3` images remain first-pass captures. The Impeccable
finish review and design-documenter handoff were not run in that session.

## Requested assistance

- ChatGPT in the in-app Browser: visible **6 Pro**, user-confirmed selection;
  planning response completed with `TASKSIGNAL_ALPHA3_PLAN_DONE` marker.
  [Planning conversation](https://chatgpt.com/c/6aa9d2b0-f570-83ea-91ac-9a786d22f380).
  Applied its recommendations for URL-backed views, evidence-first review,
  continuous queue navigation, populated-home density, and browse-first projects.
- Cursor: **Claude Fable 5.1 Max** (later displayed `1M Max`), task
  `TaskSignal alpha 3 improvement`. The initial two-file project-list work was
  followed by a completed 26-file improvement pass in `7a8c736`. That pass
  recorded 123 passing web tests and completed the browser flows listed in
  `IMPLEMENTATION-LEDGER.md`; its final handoff is visible in Cursor.
- Grok Build CLI: bounded read-only analysis completed. Verified and fixed
  false-empty thread/project/source states and premature home-demo feedback.
  Did not apply its unverified mutation-staleness suggestion.
- Impeccable and Hallmark applied to the existing Operate/workbench design;
  no new brand identity or replacement visual world was introduced.

## Historical runtime and publication boundaries

Publication target: `Yurii201811/tasksignal`, branch
`codex/tasksignal-next-version`, acting as `Yurii201811`. The 2026-09-22
instruction authorizes the bug fix, all task commits, and the branch push.
Remote publication must be checked against the resulting local HEAD; the
historical test and preview records below do not establish remote state.

- Original preview: web `http://127.0.0.1:3000`, API `http://127.0.0.1:8000`,
  packaged/fixture mode with the model provider disabled. These were temporary
  runtimes, not guaranteed-current services; Fable's later ports are in its ledger.
- No original database, unrelated checkout, authentication, or permissions changed.
- No tag, public release, deployment, remote CI, or independent usability study
  is established by this checkpoint. PostgreSQL/Docker, optional ML, and the
  full platform wheel matrix were not rerun. This is not final design sign-off.
