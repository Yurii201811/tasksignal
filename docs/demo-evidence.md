# v0.2.0 Demo Evidence Snapshot

This snapshot accompanies the `v0.2.0` release candidate and records what the
fixture demo produces without paid APIs, live credentials, private data, or
model downloads. It gives reviewers a fast way to understand the end-to-end
output before running the app locally.

The candidate is ready for public-release review only when `make verify`, the
web npm audit, a fresh smoke proof bundle, manifest verification, and the
`0.2.0` release content gate pass at the candidate commit. A Git tag and GitHub
Release are separate publication evidence; this document does not claim they
exist before the maintainer creates them. See the [release checklist](release-prep.md).

## How To Reproduce

Fast clean smoke check:

```bash
make smoke
```

This uses a temporary SQLite database and proves the complete credential-free
decision loop in this order:

1. Process fixture data, check stats and opportunities, and select the top opportunity.
1. Save that opportunity as `promising` with a local-only review note.
1. Read the baseline evaluation, append one `true_signal` evidence review with a separate local-only note, and read evaluation again.
1. Require reviewed-item count, review coverage, and the `true_signal` aggregate to increase.
1. Export task-pack JSON and evidence Markdown, require the persisted decision, evidence readiness, and `## Decision Context`, and reject either local-note sentinel from both exports.
1. Validate the eight-section task pack, confirm the dashboard route is wired, and remove the temporary database on exit.

To keep a shareable Markdown proof from the same credential-free run:

```bash
apps/api/.venv/bin/python -u scripts/first_run_smoke.py \
  --proof-out first-run-proof.md
```

The report records the API health/readiness checks, fixture counts, persisted
decision state, evidence-review count, evaluation delta, evidence readiness,
task-pack title and section contract validation, dashboard route check, and
runtime boundaries. It records that local notes were excluded without including
their values, secret values, raw connector payloads, private scan data, or local
database paths.

For a complete reviewer bundle from the same credential-free run:

```bash
apps/api/.venv/bin/python -u scripts/first_run_smoke.py \
  --proof-dir first-run-proof-bundle
```

The bundle includes `first-run-proof.md`, `first-run-summary.json`, the top
opportunity's exported task pack, and `MANIFEST.json` with file sizes and
SHA-256 hashes so reviewers can inspect both human and machine-readable
evidence from one run. The smoke run validates the task pack title, all eight
required sections, required-section order, non-empty required sections, and
duplicate required sections in the handoff contract before the generated prompt appendix, using
`skills/tasksignal-opportunity-builder/scripts/check_task_pack.py` before
writing the bundle. If the output directory already exists, it must be empty or
contain only generated proof-bundle files so stale artifacts cannot sit outside
the manifest. The generated bundle also rejects both local-note sentinels.

To verify a saved proof bundle later without rerunning the smoke pipeline:

```bash
apps/api/.venv/bin/python -u scripts/first_run_smoke.py \
  --verify-proof-dir first-run-proof-bundle
```

The verifier checks `MANIFEST.json`, required artifact presence, byte counts,
SHA-256 hashes, and unexpected top-level files.

To also boot the Next.js dev server and request `/dashboard`, run:

```bash
apps/api/.venv/bin/python -u scripts/first_run_smoke.py --with-web-server
```

Manual browser path:

```bash
make migrate
make up
```

Then open `http://localhost:3000`, go to Dashboard, and click **Process demo data**.

For API-only verification:

```bash
curl -X POST "http://localhost:8000/api/process/demo"
curl "http://localhost:8000/api/stats"
curl "http://localhost:8000/api/opportunities"
```

To force a destructive reset over the API, set `DEMO_RESET_TOKEN` and include
the matching `X-Demo-Reset-Token` header with `reset=true`.

## Reference Fixture Run Summary

The static counts below were generated from the local fixture pipeline on
2026-06-01. Release evidence uses a fresh smoke proof bundle and its verified
manifest rather than treating these historical counts as a current test run.

| Metric | Count |
| --- | ---: |
| Raw fixture records loaded | 18 |
| Normalized records created | 18 |
| Problem signals detected | 17 |
| Clusters created | 5 |
| Opportunities generated | 5 |

Source mix:

| Source | Count |
| --- | ---: |
| GitHub Issues | 4 |
| Hacker News | 4 |
| Reddit | 5 |
| Stack Exchange | 5 |

## Top Generated Opportunities

| Score | Opportunity | Suggested MVP |
| ---: | --- | --- |
| 56 | Operators need spreadsheet-to-client-report automation | CSV-to-report workflow builder with reusable transforms, checks, and branded Markdown/PDF output. |
| 49 | Small SaaS teams need simple onboarding drop-off analysis | Lightweight event import and funnel explainer that highlights the first confusing step and suggests experiments. |
| 46 | Developers need clearer GitHub Actions failure diagnosis | CI log summarizer and workflow linter that identifies likely YAML mistakes, dependency failures, and next fixes. |
| 42 | AI-generated code needs production-readiness audits | GitHub repo scanner that flags missing tests, duplicated logic, fragile error handling, and suspicious generated code patterns. |
| 42 | Founders need a cheaper lead and community signal radar | Source-aware inbox that ranks public posts by relevance, pain intensity, buying intent, and safe reply timing. |

## What Reviewers Should Check

- The demo path runs without paid AI APIs.
- Generated prompts include source excerpts, scoring rationale, and privacy constraints.
- Evidence references public source URLs when available.
- Raw usernames are not stored or exported by default; normalized records use `author_hash`.
- Opportunity and evidence review notes are local-only and are excluded from evidence and task-pack exports.
- The evaluation evidence proves a selected review loop; its coverage and reviewed-positive precision are not recall, F1, or market validation.
- Live connectors are optional and keep the same reviewable scoring/generation path.

## Live Connector Smoke Test

The default public live scan uses Hacker News, which does not require server-side
credentials:

```bash
curl -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -d '{"source":"hackernews","query":"ask","limit":30}'
```

This should create a completed scan record, save public Hacker News records,
detect repeated workflow signals, and generate at least one opportunity when
enough related signals are returned. Credentialed connectors such as GitHub and
Reddit are reserved for trusted internal jobs.

Live public feeds are not fixtures. A scan can complete, save records, and still
generate zero opportunities when the returned posts do not contain enough
related problem signals. In that case, scan records expose `signals_detected`,
`clusters_created`, `opportunities_created`, and `outcome_message` so reviewers
can distinguish a working connector from weak source/query fit.

## Current Limits

- This is a fixture/demo snapshot, not evidence of broad adoption.
- Scores are transparent MVP heuristics, not model-backed market validation.
- The project needs external testers, issue feedback, and real-world usage before making adoption claims.
