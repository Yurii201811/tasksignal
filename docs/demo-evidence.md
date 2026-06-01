# Demo Evidence Snapshot

This snapshot records what the fixture demo produces without paid APIs, live credentials, private data, or model downloads. It gives reviewers a fast way to understand the end-to-end output before running the app locally.

## How To Reproduce

```bash
cp .env.example .env
make up
```

Then open `http://localhost:3000`, go to Dashboard, and click **Process demo data**.

For API-only verification:

```bash
curl -X POST "http://localhost:8000/api/process/demo?reset=true"
curl "http://localhost:8000/api/stats"
curl "http://localhost:8000/api/opportunities"
```

## Fixture Run Summary

Snapshot generated from the local fixture pipeline on 2026-06-01.

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
- Live connectors are optional and keep the same reviewable scoring/generation path.

## Live Connector Smoke Test

The default live scan is a no-credential GitHub Issues search:

```bash
curl -X POST "http://localhost:8000/api/scans" \
  -H "Content-Type: application/json" \
  -d '{"source":"github","query":"manually copy paste is:issue is:open","limit":30}'
```

This should create a completed scan record, save public GitHub issue records, detect repeated workflow signals, and generate at least one opportunity when enough related signals are returned. GitHub rate limits may apply when no `GITHUB_TOKEN` is configured.

## Current Limits

- This is a fixture/demo snapshot, not evidence of broad adoption.
- Scores are transparent MVP heuristics, not model-backed market validation.
- The project needs external testers, issue feedback, and real-world usage before making adoption claims.
