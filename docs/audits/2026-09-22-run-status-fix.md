# Project run status fix verification

Date: 2026-09-22. Branch: `codex/tasksignal-next-version`.
Starting commit: `7a8c736` (Fable's completed alpha 3 improvement pass).

## Change

The API records connector failures as scan objects with `status: failed` and
returns them with HTTP 200. Run history previously treated any returned scan as
a success. The response banner now derives its tone and title from scan status:

- `failed`: error alert, connector error and outcome message, scan-detail link.
- `completed`: success confirmation and counts.
- Other statuses, including `queued` and `running`: neutral response notice,
  with the actual status and no completion claim.

All responses continue refreshing project history and the shared research
caches. No API, authorization, database, or connector behavior changed.

## Verification

- Before the fix, a temporary regression test reproduced the green success
  message for a failed scan response.
- `npm test -- tests/project-run-history.test.tsx`: **8 passed**, including
  failures with/without an outcome message, queued/running results, successful
  reruns, cache invalidation, and load recovery.
- Full web `npm test`: **127 passed in 24 files** on Node 20.
- `tsc --noEmit`, ESLint, and `git diff --check`: passed.
- Next.js production build: passed, 14 static pages generated. Built from an
  isolated copy of the current web source with the same dependencies, using a
  loopback fixture API URL; no environment files were copied.
- In-app Browser: clicked **Run project** against a synthetic loopback API
  returning HTTP 200 plus a failed scan. Confirmed the red **Project run failed**
  banner, connector message, scan link, and refreshed failed ledger row.
  A separate completed response retained its successful confirmation and counts.
  Both temporary preview processes were stopped and the test tab closed.
- `scripts/release_check.py`: passed for documentation, tracked-file checks,
  secret-pattern scan, version metadata, and changelog. No CI run URL supplied.
- The preceding 2026-09-22 review also reran `make smoke`: 18 raw items,
  17 signals, 5 opportunities, zero false threads on identical rerun, and a
  verified ten-file packet. The backend and smoke inputs are unchanged by this fix.

The two existing fixture screenshots under `.impeccable/review/alpha3/` are
included and labelled as historical first-pass evidence, not screenshots of
this fix or final visual approval.

## Publication and limitations

The user explicitly requested committing all task changes and pushing to
`Yurii201811/tasksignal` on the existing feature branch. The branch includes
the earlier alpha improvements and Fable's commit as well as this repair.
Verify the remote branch SHA against local HEAD after pushing.

This check does not claim a merge, tag, release, deployment, live connector
verification, or final Impeccable/design-documenter review. The remaining
design and release limitations are recorded in the alpha 3 implementation ledger.
