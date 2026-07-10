# Product Brief

## Product Thesis

TaskSignal is an evidence-backed problem discovery engine. It turns public discussions into ranked software opportunity cards and Codex-ready task packs. The product is strongest when it acts as a research workbench: collect public signals, show why they were scored, preserve source attribution, and export a bounded build prompt.

The current product should not be reframed as a generic "AI idea generator." Its differentiator is the evidence trail: source URLs, detector spans, score breakdowns, rank drivers, and privacy constraints are surfaced throughout the workflow.

## Current Positioning

Source files:

- `README.md`
- `PRODUCT.md`
- `DESIGN.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/data-ethics.md`
- `docs/model-card.md`

Current status from `README.md`: portfolio-ready MVP, early public application repository, designed for one local operator on their own machine. Fixture data works without API keys. Live connectors are optional and use official APIs when configured.

The repo explicitly says TaskSignal is not for:

- scraping private communities
- profiling individuals
- spam or outreach automation
- replacing human product judgment
- storing raw usernames by default

## Primary Users

- Builders and indie hackers looking for concrete MVP opportunities.
- Developer-tool founders researching repeated pain in public communities.
- Product managers validating whether a workflow complaint repeats across sources.
- Researchers who need auditable source trails before recommending what to build.
- Codex users who want build-ready prompts grounded in source evidence.

## Core Jobs To Be Done

1. Find public problem signals from fixtures or live public sources.
2. Save repeatable research workflows with source, query, cadence, labels, and limits.
3. Inspect ranked opportunities with evidence, source mix, and score breakdowns.
4. Search normalized evidence semantically.
5. Export prompts, evidence bundles, and task packs for Codex or another coding agent.
6. Maintain local privacy boundaries while using optional credentials or model runtimes.

## Current Product Strengths

- Clear local-first posture and trust boundary.
- Good documentation for a small MVP.
- Fixture demo path makes first-run review credible.
- Saved research projects make the app more than a one-off scanner.
- Scan records preserve zero-opportunity and failure outcomes.
- Opportunity detail page exposes score components and evidence.
- Prompt/task-pack export path is useful and reviewable.
- Integration/readiness surfaces avoid exposing secret values.
- Public scan API defaults to non-credentialed sources.

## Current Product Fragility

- The product value depends on heuristic detector and clustering quality.
- Semantic search is item-only today; it does not retrieve opportunities despite returning an `opportunities` field.
- Prompt enhancement has a UX/API mismatch: the API requires an operator token, but the web action does not pass one.
- The dashboard is strong for demo/review, but it does not yet help users compare scan runs or decide whether an idea is validated.
- Source enablement state is displayed but should be reviewed for whether it is enforced consistently.
- Hosted mode would need a different trust model: auth, tenant boundaries, retention, audit logs, and stricter token handling.

## Product North Star

"From repeated public pain to an auditable build decision."

Useful next-version metric candidates:

- Percent of generated opportunities with at least N evidence items and source URLs.
- Reviewer agreement rate on problem-signal labels.
- False-positive rate for detector output.
- Number of repeatable projects with successful scan history.
- Number of exported task packs that include evidence, ranking rationale, and privacy constraints.
- Time from fresh checkout to first useful task pack.
