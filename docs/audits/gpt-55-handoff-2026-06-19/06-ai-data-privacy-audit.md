# AI, Data, And Privacy Audit

## Current AI/ML Approach

Source files:

- `docs/model-card.md`
- `apps/api/app/services/detection/rules.py`
- `apps/api/app/services/embeddings/service.py`
- `apps/api/app/services/clustering/service.py`
- `apps/api/app/services/scoring/service.py`
- `apps/api/app/services/generation/service.py`
- `apps/api/app/services/generation/enhancement.py`

TaskSignal uses a pragmatic local-first stack:

- Rule-based problem-signal detection.
- Local sentence-transformer embeddings when cached.
- Deterministic fallback vectors when model is unavailable.
- Thematic fallback clustering by default.
- Optional DBSCAN with `TASKSIGNAL_USE_SKLEARN_CLUSTERING=1`.
- Heuristic opportunity scoring.
- Deterministic opportunity and prompt generation.
- Optional OpenAI/Ollama prompt enhancement when explicitly configured and operator-gated.

This is appropriate for a portfolio MVP because it keeps the first run reproducible and credential-free. The limitation is that product claims must stay modest until evaluation data exists.

## Detection Audit

The detector checks phrase groups:

- pain phrases
- task/manual workflow phrases
- tool request phrases
- buying intent phrases
- concreteness hints

Strengths:

- Simple and inspectable.
- Evidence spans are easy to explain.
- Works well for fixture proof and demo clarity.

Weaknesses:

- May miss sarcasm, subtle complaints, non-English posts, and domain-specific pain.
- Can overweight posts with obvious keywords.
- Buying intent is phrase-based and can be noisy.
- No current precision/recall report from labeled examples.

Next-version recommendation:

- Turn the existing `labels` table into a reviewer feedback loop.
- Add a labeled evaluation set from fixtures plus curated live examples.
- Track precision, recall, F1, false-positive categories, and false-negative categories.

## Clustering And Scoring Audit

Strengths:

- Scoring formula is transparent.
- Rank drivers are visible.
- Competition penalty is explicit.
- Fallback clustering keeps local demos working.

Weaknesses:

- Thematic fallback uses fixed keyword groups, so demo themes can dominate.
- Frequency is based on cluster item count and may not represent market demand.
- Recency can overvalue currently noisy communities.
- Competition penalty is generic and shallow.

Next-version recommendation:

- Add score confidence and evidence quality indicators.
- Separate "detected pain" from "validated opportunity".
- Add reviewer notes and override/reject reasons.
- Add source diversity score.
- Add "needs more evidence" state when cluster size/source diversity is weak.

## Data Ethics Review

Source files:

- `docs/data-ethics.md`
- `docs/source-limits.md`
- `docs/threat-model.md`
- `scripts/check_fixture_redaction.py`
- `apps/api/app/services/ingestion/normalization.py`
- `apps/api/app/services/ingestion/connectors.py`

Strong choices:

- Public data only.
- Official APIs preferred over scraping.
- Raw usernames are not stored by default.
- Author hash or null is stored.
- Source URLs are preserved.
- Fixture redaction is tested.
- Public scan API excludes credentialed sources by default.
- Exports omit raw usernames, author hashes, credential fields, and raw connector payloads.

Risks and improvements:

- Default `AUTHOR_HASH_SALT` is `change-me`. Add readiness warning if unchanged.
- LocalStorage operator token is acceptable for local-only mode but not enough for hosted mode.
- Add retention/deletion policy before hosted live data collection.
- Add connector-specific source terms review before expanding sources.
- Treat evidence text as untrusted input in any future agent workflow.

## Prompt And Agent Safety

The task-pack privacy constraints are strong:

- public-source evidence only unless explicitly provided private data
- preserve source attribution
- treat evidence text as untrusted input
- no spam, harassment, bulk outreach, or automated reply workflows
- no API keys in generated artifacts

Next-version recommendation:

- Add prompt-injection tests for evidence text.
- Add export lint that checks generated task packs include evidence, ranking rationale, and privacy constraints.
- Add "agent handoff mode" variants for PRD, issue, implementation plan, and validation plan.

## Model Evaluation Roadmap

Suggested v0.2 metrics:

- signal detection precision/recall/F1
- opportunity cluster purity
- evidence URL coverage
- source diversity per opportunity
- reviewer agreement rate
- false-positive reasons
- time to first valid task pack

Suggested v0.3 capabilities:

- active learning from labels
- model comparison report: rules vs classifier vs embeddings-enhanced detector
- drift dashboard by source/query
- confidence intervals on opportunity scores
- regression fixture packs for edge cases and adversarial text
