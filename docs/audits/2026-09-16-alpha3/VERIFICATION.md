# TaskSignal alpha 3 verification checkpoint

Date: 2026-09-16 (Europe/Stockholm).
Branch: `codex/tasksignal-next-version`.
Base: `d9d55223246fcb933c3884a7781ed2107aa781ef`.
Worktree: `/Users/yuriibakurov/Documents/Github Project/tasksignal/.worktrees/tasksignal-next-improvement`.
Version: Python `1.0.0a3`; web `1.0.0-alpha.3`.

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

## Completed verification

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

**Pending:** the Mac locked during the unsaved-navigation warning check. Browser
and native-app tools could no longer inspect or dismiss the prompt. The user was
asked to unlock the Mac. Do not report the final responsive pass, save-and-next
readback, console check, Impeccable finish review, or design-documenter
handoff as complete yet. Existing `.impeccable/review/alpha3` images are first-pass
captures, not final review evidence.

After unlock: dismiss any pending warning while keeping the draft, save it,
verify next/back behavior, reload the production preview, capture desktop and
320/375/390/414/768px plus the user's viewport, and complete the skill finish
review. Reset viewport override and keep the preview tab as the deliverable.

## Requested assistance

- ChatGPT in the in-app Browser: visible **6 Pro**, user-confirmed selection;
  planning response completed with `TASKSIGNAL_ALPHA3_PLAN_DONE` marker.
  [Planning conversation](https://chatgpt.com/c/6aa9d2b0-f570-83ea-91ac-9a786d22f380).
  Applied its recommendations for URL-backed views, evidence-first review,
  continuous queue navigation, populated-home density, and browse-first projects.
- Cursor: **Claude Fable 5.1 Max** (later displayed `1M Max`), task
  `TaskSignal alpha 3 improvement`. It exclusively changed
  `research-projects.tsx` and its eight-test suite, which passed. Its temporary
  preview-tab cleanup was requested; final UI confirmation awaits unlock.
- Grok Build CLI: bounded read-only analysis completed. Verified and fixed
  false-empty thread/project/source states and premature home-demo feedback.
  Did not apply its unverified mutation-staleness suggestion.
- Impeccable and Hallmark applied to the existing Operate/workbench design;
  no new brand identity or replacement visual world was introduced.

## Runtime and boundaries

The user subsequently authorized implementing the remaining recommendations,
committing all task changes, and pushing them to GitHub after completion. Target:
`Yurii201811/tasksignal`, current branch `codex/tasksignal-next-version`. GitHub
actor was verified as `Yurii201811`; the remote branch does not yet exist. The
push remains pending the final browser/design review. No further push approval
is needed for this scope. Latest local implementation checkpoint: `08f0c5e`.

- Production Next preview: `http://127.0.0.1:3000`, exec session `98181`.
- API: `http://127.0.0.1:8000`, exec session `7580`, packaged/fixture mode,
  model provider disabled. These session IDs are only valid for this live run.
- No original database, unrelated checkout, authentication, or permissions changed.
- No push, tag, public release, deployment, remote CI, or independent usability
  study. PostgreSQL/Docker, optional ML, and the full platform wheel matrix were
  not rerun. The local checkpoint is not final visual sign-off.
