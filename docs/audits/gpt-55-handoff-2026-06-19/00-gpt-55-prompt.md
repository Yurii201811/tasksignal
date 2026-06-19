# Copy-Ready Prompt For GPT 5.5 Pro

You are auditing TaskSignal, a local-first AI problem discovery engine. Your job is to propose practical product improvements, code changes, and next-version direction based only on the attached audit context and source-grounded notes.

## Product Summary

TaskSignal mines public developer/community discussions, detects repeated painful workflows, clusters related problem signals, scores opportunities, and exports Codex-ready prompts/task packs with evidence and privacy constraints. It is currently positioned as a portfolio-ready MVP for one local operator, not a multi-tenant SaaS.

Primary user: developer, founder, indie hacker, product manager, or researcher looking for evidence-backed software ideas from public discussions.

Primary workflow: configure local workspace and source query, run fixture or public scans, inspect ranked opportunities, review evidence and scoring, export a Codex prompt or task pack.

## Hard Constraints

- Preserve the local-first, research-grade posture unless you explicitly recommend a separate hosted mode.
- Do not recommend spam, outreach automation, profiling, scraping private communities, or storing raw usernames.
- Treat scores as heuristic review aids, not market validation.
- Keep recommendations source-faithful: separate implemented features from proposed improvements.
- Prefer high-leverage, realistic improvements over generic AI-dashboard ideas.
- If proposing hosted/SaaS features, include required auth, retention, rate-limit, and privacy changes.

## What I Want From You

Produce a concise but deep improvement plan with:

1. Executive assessment: what is strong, what is fragile, and what should not change.
2. Top 10 product improvements, ranked by impact and effort.
3. Top 10 technical changes, ranked by risk reduction and product leverage.
4. Suggested v0.2 scope: what to ship next in 2-4 weeks.
5. Suggested v0.3 scope: what to ship after v0.2.
6. UX improvements for the current dashboard, projects, scans, search, integrations, opportunity detail, and prompt export surfaces.
7. AI/model/evaluation improvements that keep the app auditable.
8. Security/privacy hardening list, especially for any hosted mode.
9. Tests or acceptance criteria for each major recommendation.
10. A one-page "next version product brief" suitable for a GitHub issue or PRD.

## Important Source-Grounded Findings To Account For

- Verification is mostly healthy: `make verify`, `doctor`, release check, smoke, API tests, web tests, lint, and build passed locally after one test-source false-positive fix.
- `npm audit` reports two current frontend dependency advisories: `js-yaml` moderate and `undici` high.
- API prompt enhancement is gated by `X-Operator-Scan-Token`, but the current web helper/action does not pass the operator token for "Enhance Prompt".
- Semantic search currently returns ranked evidence items but an empty `opportunities` array.
- Detection, clustering, and scoring are intentionally heuristic and local-first; the next version should add evaluation and reviewer feedback before making stronger claims.
- The public scan API is restricted to browser-safe sources by default; credentialed scans require operator token paths.
- The app stores author hashes rather than raw usernames by default and exports evidence without raw identities or secret values.

## Output Style

Be specific. Cite the relevant audited files by path when useful. For each major recommendation, include "why now", "what to change", "acceptance criteria", and "risk if ignored".
