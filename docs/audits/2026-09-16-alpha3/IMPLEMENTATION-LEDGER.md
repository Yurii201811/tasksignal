# TaskSignal alpha 3 implementation ledger

Date: 2026-09-16 (Europe/Stockholm). Branch: `codex/tasksignal-next-version`.
Base for this pass: `ff31e22`. Worker: Cursor (Claude Fable 5.1, Max), acting as
the single implementer with the Codex coordinator read-only.

This ledger reconciles the alpha 3 recommendations with the code that actually
shipped, records what this pass changed, and lists what remains open with the
reason. It does not claim measured speed gains, a public release, or an
independent usability result.

## Completed in this pass

Reliability and honest data states:

- Scan history, project run history, agent sessions, and the source registry no
  longer show an empty-state claim when the request failed. Each failed load
  shows the API error detail with a Retry action; stale data, when present,
  stays visible with a note.
- Queue, threads list, evidence search, prompt view, and Sources render the
  parsed API error detail instead of the raw JSON error body.
- Build Studio surfaces failed stored-packet and packet-artifact loads with
  Retry, shows a loading state, and tells an eligible thread when no packet
  exists yet.
- Integrations page surfaces failed integration, readiness, and workspace-profile
  loads with Retry, and keeps **Save workspace** disabled until the stored
  profile has loaded so an unseen profile cannot be overwritten.
- Evaluation and generated-prompt load failures offer Retry.
- Discourse forums keep their own display names on the Sources page.

Navigation and evidence-first coherence:

- Thread pages add **Review evidence** (current snapshot), an **Open snapshot
  evidence** link on every historical snapshot, a **Thread decision saved**
  confirmation with a last-saved timestamp, a disabled Save while clean, and the
  same unsaved-edit warning the opportunity page uses.
- Threads list distinguishes "No opportunity threads yet" (with a link to run a
  project) from "No threads match this review state" (with a reset action).
- Project run history adds **Run project** (same cache refresh as the projects
  page), **Open queue for this project**, a scan-status badge, and a **Scan
  detail** link per run; the rerun result links to its scan.
- Project cards add **Open queue** once a project has at least one run.
- Project-run cache refresh is centralized in `refreshProjectRunQueries`
  (`apps/web/src/lib/research-cache.ts`) and shared by the projects page and run
  history.

Responsive:

- The opportunity score card stacks below the `sm` breakpoint. At 320px it
  previously squeezed its description into a one-word-per-line column (found in
  the browser pass, fixed, and re-captured).

Documentation:

- README headline section updated from "alpha 2" to alpha 3 content.
- CHANGELOG 1.0.0a3 gains the additions and fixes above.
- This ledger; `VERIFICATION.md` pending items closed below.

## Verified in this pass

Web unit tests: **123 passed** in 24 files (was 106 in 22). New or extended
suites: `sources`, `settings`, `scans`, `project-run-history`, `agent-sessions`,
`opportunity-threads`, `research-projects`.

`make verify`: passed — 535 backend tests (isolated temporary SQLite), 123 web
tests, fixture redaction check, Ruff, ESLint, TypeScript, production Next build
(14 routes). `make smoke`: passed — 18 raw items, 17 signals, 5 opportunities,
identical rerun with 0 false new threads, actor-aware labels distinct, ten-file
packet with 14 private markers excluded and server-verified.

Browser checks ran in the in-app Cursor Browser against a **new disposable**
database `/tmp/tasksignal-alpha3-fable-20260916-204425.db` (API
`http://127.0.0.1:8010`, web `http://127.0.0.1:3010`, clean URLs, no mocked
responses). The original workspace database was not used.

| Check | Result |
| --- | --- |
| Empty home → **Try demo data** | Totals updated live to 18 / 17 / 5 / 0; onboarding collapsed after population. |
| Create fixture project → **Run** | Card refreshed to `completed`, Runs 1, filter counts recounted, latest-scan badge updated, **Scan detail** / **Open queue** appeared without reload. |
| Run history → **Run project** | Ledger gained Run 2 in place; Run 2 delta showed 6 seen before / 6 unchanged / 2 threads unchanged. |
| Project-scoped queue | `/dashboard?project=…` filtered to 2 rows; every row and **Review next** carried the queue context. |
| Dirty draft | Changing the decision disabled **Next in this queue** with the save-first hint. |
| Unsaved-navigation warning (previously pending) | Clicking Home fired `Discard unsaved review changes and leave this page?`; answering "stay" kept the page and the Promising draft. `window.confirm` was intercepted in the preview tab only, after approval, so the native dialog could not block the session. |
| Save decision readback | **Decision saved**, `Confirmed: Promising`, timestamp and note retained, Next re-enabled. |
| Next / Back | Next opened the second item in the same view; end-of-view message shown there; **Back to filtered queue** returned to the scoped URL with the saved decision reflected (Promising 1, New 1). |
| Thread save → packet | Thread saved as Build candidate with the new confirmation; Build Studio flipped to Eligible; deterministic packet generated with 10 artifacts; **Integrity verified**. |
| Cross-view consistency | Thread decision showed as `Confirmed: Build candidate` on the snapshot page and in the queue after reload. |
| 320px | Home, queue, projects, opportunity page: no horizontal overflow (measured `scrollWidth === clientWidth`). |
| 768px | Threads page: no page overflow; the threads table scrolls inside its own labelled region only. |
| Console | Clean loads reported zero Next dev-overlay issues on home, queue, projects, opportunity, and threads. One hydration warning appeared only when the browser tool tagged the DOM (`data-cursor-ref`) before React hydrated; it is a tooling artifact, not app code. |
| Production preview | Rebuilt with the preview API base and reloaded; bookmarked scoped view and saved decisions read back from the database with no dev overlay. |

Captures from this pass are in the Cursor screenshot folder
(`alpha3-fable-*.png`); the earlier `.impeccable/review/alpha3` images remain
first-pass captures and were not modified.

## Already done before this pass (verified, not changed)

- URL-backed queue views, copy-link, filtered return path, continuous Next.
- Unsaved-review guard and Next lockout on the opportunity page.
- Review invalidation across snapshot, thread, evaluation, and readiness views.
- Browse-first projects with search, run-status filters, and the creation
  disclosure; honest pending / failed / empty Discourse source states.
- False-empty fixes for the threads list and projects list.
- Populated-home density with empty-only onboarding.

## Deferred (with reason)

- Responsive card layout for the threads and run-history tables. Both tables
  scroll inside their own labelled region, which the UI rules allow; a row-based
  layout is a larger redesign than this pass should carry.
- Screenshot captures at 375/390/414px. Overflow was measured programmatically at
  the most constraining width (320px) and at 768px; intermediate widths share
  the same breakpoints.
- Impeccable finish review and design-documenter handoff. Those skills were not
  invoked in this pass; no new visual world was introduced, and the static
  detector report in `DETECTOR.json` stands.
- Evidence-search hits do not link to a queue or snapshot; the hit carries scan,
  run, and project provenance but no opportunity identifier, so a link would
  require an API change.
- Threads list at 320px was not screenshot; its table region scrolls as designed.

## Blocked / not attempted (with reason)

- Push, PR, tag, deployment, remote CI, PostgreSQL/Docker, optional ML extra,
  and the platform wheel matrix: outside this local, reversible scope.
- Independent usability sessions: no participants or artifacts exist; nothing
  is claimed.
- Live credentialed connectors (GitHub, Reddit, Stack Exchange, Discourse): no
  credentials or authorized hosts were used; only fixture and demo paths ran.

## Preview runtime

- API: `http://127.0.0.1:8010`, disposable database above, fixture mode, model
  provider disabled, operator token set locally for the preview only.
- Web: production build served on `http://127.0.0.1:3010` with
  `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010`.
- Both processes run detached (session leaders); PIDs are recorded in
  `/tmp/tasksignal-fable-preview-pids.txt`. Stopping them and deleting the
  `/tmp/tasksignal-alpha3-fable-*` files fully reverses the preview.
