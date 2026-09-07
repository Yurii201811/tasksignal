# TaskSignal First-Run Proof

Generated: 2026-09-07T22:41:18+00:00
Repository revision: codex/tasksignal-next-version @ eb11c5821754 (local changes present)

Scope: credential-free fixture smoke run against a temporary SQLite database.

## Checks

| Check | Result | Evidence |
| --- | --- | --- |
| API health | passed | status=ok |
| Readiness endpoint | passed | status=ready |
| Fixture demo processing | passed | 18 raw records, 18 normalized records, 17 signals, 5 clusters, 5 opportunities |
| Stats endpoint | passed | 18 total items, 10 opportunities |
| Task-pack export | passed | 4 evidence URL(s) on the top opportunity |
| Task-pack structure | passed | 8 required sections present, validated by `skills/tasksignal-opportunity-builder/scripts/check_task_pack.py` |
| Decision review workflow | passed | state=promising, 2 reviewed evidence items, reviewed items=0->2, coverage=0%->12%, readiness=medium, local notes excluded |
| Longitudinal research memory | passed | 2 runs, identical rerun: new=0, seen before=18, updated=0, unchanged=18, not observed=0; threads=5->5, exact matches=5, false new threads=0 |
| Actor-aware evidence review | passed | human labels=2, agent labels=1, human precision=1.0->1.0, readiness=medium->medium; agent self-grading excluded |
| Immutable build packet | passed | state=build_candidate, mode=deterministic, files=10, archive bytes=10525, server verified=true, repeat download identical |
| Build-packet privacy | passed | 14 private markers checked; categories={'author_hashes': 4, 'local_notes': 3, 'raw_identities': 4, 'secret_values': 3}; local notes, raw identities, author hashes, and secret values excluded |
| Dashboard route source | passed | route imports the dashboard feature |
| Live dashboard request | skipped | not requested |

## Source Mix

| Source | Count |
| --- | ---: |
| github | 4 |
| hackernews | 4 |
| reddit | 5 |
| stackexchange | 5 |

## Top Opportunity

- Operators need spreadsheet-to-client-report automation

## Runtime Boundaries

- LLM_PROVIDER=none
- PUBLIC_SCAN_SOURCES=fixture,hackernews
- Database: temporary SQLite file created for this smoke run.
- Secrets, raw connector payloads, local database paths, and private scan data are omitted.

## Follow-Up

- For UI confidence, rerun with `--with-web-server` so the script boots Next.js and requests `/dashboard`.
- For release evidence, pair this proof with `make release-check` and the relevant GitHub Actions run URL.
