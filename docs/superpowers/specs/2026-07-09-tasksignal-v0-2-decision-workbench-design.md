# TaskSignal v0.2 Decision Workbench Design

Date: 2026-07-09
Status: Approved product direction; pending written-spec review before implementation

## Summary

TaskSignal v0.2 will turn the current evidence-generation workflow into a local
research-decision workbench. The operator will be able to classify an
opportunity, record a local decision note, review the evidence behind it, see
an honest aggregate evaluation summary, filter the opportunity queue by decision
state, and export decision-aware artifacts.

The release remains local-first and single-operator. It will not add accounts,
hosted collaboration, private-source ingestion, automatic build decisions, or a
paid-model requirement.

## Problem

TaskSignal currently finds, scores, explains, and exports opportunities, but the
review step is passive:

- `Opportunity` has no persisted decision state or review note.
- Evidence labels accept arbitrary strings and are exposed only through a
  create-only endpoint.
- The dashboard ranks opportunities but cannot act as a decision queue.
- Exported task packs do not say whether an opportunity is new, rejected,
  promising, or ready to build.
- The model card proposes evaluation metrics, but the product has no review
  workflow from which honest metrics can be calculated.

This leaves a gap between "TaskSignal generated an interesting card" and "the
operator made an auditable product decision."

## Goals

1. Make opportunity review persistent, explicit, and useful from the dashboard
   and opportunity detail page.
2. Turn the existing `labels` table into a constrained, append-only evidence
   review history.
3. Show evidence readiness as transparent checks rather than another opaque
   market score.
4. Report only evaluation metrics that the available reviewed data can support.
5. Carry safe decision context into task-pack and evidence exports.
6. Make local setup and the full verification path reproducible on this checkout.
7. Deliver the work as development version `0.2.0`, without publishing a tag or
   GitHub release.

## Non-Goals

- Multi-user authentication, authorization, or workspace isolation.
- Hosted background workers or remote team collaboration.
- Automatic approval, rejection, issue creation, outreach, or implementation.
- Private-community scraping or new source connectors.
- Training a new classifier or claiming global precision, recall, or market
  validation.
- Scan-to-project lineage and historical scan delta views.
- MCP, new agent protocols, or additional export formats. The generated prompt
  content remains unchanged; v0.2 enriches task-pack and evidence exports.
- Unrelated UI redesign or broad backend refactoring.

## Product Contract

### Opportunity decision states

Every opportunity has exactly one current state:

| Value | Meaning |
| --- | --- |
| `new` | No current disposition; either untouched or deliberately returned to the inbox. |
| `needs_more_evidence` | Interesting, but the evidence is not sufficient for a decision. |
| `promising` | Worth further validation or planning. |
| `rejected` | Reviewed and not worth pursuing now. |
| `duplicate` | Substantially overlaps another opportunity. |
| `build_candidate` | Approved by the local operator for implementation planning. |

New and migrated opportunities default to `new`. The operator may save an
optional local note of at most 1,000 characters. Saving a state or note sets
`decision_updated_at` to the current UTC time. This timestamp records the last
explicit decision-form save, including a deliberate reset to `new`; it does not
claim that a `new` opportunity has a completed review. Subsequent saves replace
the current state and local note; v0.2 does not add opportunity-state history.

The local single-operator posture makes last-write-wins behavior acceptable for
opportunity state. State transitions are never automatic: scoring,
regeneration, prompt enhancement, and evidence labeling cannot promote an
opportunity to `build_candidate` or reject it.

### Evidence review labels

Evidence reviews use the existing `Label` model as append-only history. New API
writes accept only these labels:

| Value | Meaning |
| --- | --- |
| `true_signal` | The item is a genuine problem or workflow signal. |
| `false_positive` | The detector classified the item as a signal incorrectly. |
| `unclear` | The reviewer cannot decide from the available context. |
| `duplicate` | The evidence repeats another reviewed item. |
| `not_actionable` | The pain may be real, but it does not support a useful product action. |
| `sensitive_risk` | The item should not be used without additional privacy or safety review. |

Each review may include a note of at most 500 characters. A new review appends a
row; it never edits or deletes an earlier row. The latest stored label for an
item is the newest row ordered by `created_at DESC, id DESC`, so ties are
deterministic.

Existing database rows with labels outside the new taxonomy remain intact.
They are returned in history, counted as unrecognized by evaluation, and never
treated as the current recognized review state. If the latest stored row is
unrecognized, the item's current recognized label is `null`; the service does
not fall back to an older recognized row. New writes with unknown labels are
rejected.

### Evidence readiness

Evidence readiness measures whether an opportunity is ready for human review.
It does not estimate demand, adoption, revenue, or implementation success.

The API returns four named checks:

1. `enough_evidence`: at least five linked evidence items.
2. `source_diversity`: at least two distinct sources.
3. `source_url_coverage`: at least 80% of linked items have a safe HTTP(S)
   source URL.
4. `human_review_coverage`: at least 50% of linked items have a recognized
   current evidence label.

The readiness level is:

- `strong` when all four checks pass and no current evidence label is
  `sensitive_risk`.
- `medium` when at least two checks pass and no current evidence label is
  `sensitive_risk`.
- `weak` otherwise.

The response includes the raw counts, coverage ratios, passed checks, and gaps.
The UI and exports must call this "evidence readiness," not "confidence" or
"validation score."

`EvidenceReadinessOut` has this exact shape:

```json
{
  "level": "medium",
  "evidence_count": 5,
  "source_count": 2,
  "safe_url_count": 4,
  "reviewed_count": 2,
  "source_url_coverage": 0.8,
  "human_review_coverage": 0.4,
  "checks": {
    "enough_evidence": true,
    "source_diversity": true,
    "source_url_coverage": true,
    "human_review_coverage": false
  },
  "passed_checks": [
    "enough_evidence",
    "source_diversity",
    "source_url_coverage"
  ],
  "gaps": ["Review 1 more evidence item."]
}
```

Coverage values are floats from `0.0` through `1.0`. Counts are non-negative
integers. `checks` always contains exactly the four named keys. Passed checks
follow the order above. Gaps follow the same check order and use these templates:

- `Collect {count} more evidence item(s).` for `enough_evidence`;
- `Add evidence from {count} more source(s).` for `source_diversity`;
- `Increase safe source URL coverage to at least 80%.` for
  `source_url_coverage`;
- `Review {count} more evidence item(s).` for `human_review_coverage`;
- `Resolve or exclude evidence marked sensitive risk before advancing.` as the
  final gap whenever the sensitive-risk override applies.

The implementation uses `item`/`items` and `source`/`sources` grammatically for
counts of one versus other counts.

### Evaluation summary

The evaluation denominator is the set of distinct normalized items linked to at
least one generated opportunity. This matches the evidence that the operator can
actually review in the v0.2 UI.

The evaluation response contains:

- total reviewable evidence items;
- items with a recognized current review label;
- review coverage;
- a count for each recognized label;
- count of items whose latest stored label is unrecognized;
- source and signal-type breakdowns;
- precision on reviewed predicted-positive evidence, calculated as
  `true_signal / (true_signal + false_positive)`;
- a fixed warning explaining that manually selected reviews are subject to
  selection bias.

The precision field is `null` when there are no `true_signal` or
`false_positive` reviews. `unclear`, `duplicate`, `not_actionable`, and
`sensitive_risk` are reported but excluded from this precision denominator.
TaskSignal will not report recall or F1 in v0.2 because it has no reviewed
negative population from which those metrics could be calculated honestly.

`EvaluationSliceOut` has these fields:

- `total_items`: non-negative integer;
- `reviewed_items`: non-negative integer;
- `review_coverage`: float from `0.0` through `1.0`;
- `label_counts`: object containing all six recognized label keys with
  non-negative integer values, including zero values;
- `precision_on_reviewed_positives`: float from `0.0` through `1.0`, or `null`
  under the denominator rule above.

`EvaluationOut` has these fields:

- `total_reviewable_items`;
- `reviewed_items`;
- `review_coverage`;
- `label_counts` with all six recognized keys;
- `unrecognized_latest_labels`;
- `precision_on_reviewed_positives`;
- `by_source: dict[str, EvaluationSliceOut]`;
- `by_signal_type: dict[str, EvaluationSliceOut]`;
- `selection_bias_warning` containing exactly: `Metrics describe only manually
  reviewed evidence and may not represent all detected items.`

The top-level numeric fields use the same types and precision rules as
`EvaluationSliceOut`. Breakdown keys are sorted lexicographically in serialized
responses. Each slice uses only items in that source or signal type, and an item
appears once in each applicable top-level dimension. Empty databases return
zero counts, empty breakdown objects, `0.0` coverage, and `null` precision. A
missing or blank source or signal type is serialized under the key `unknown`.

## Architecture

The implementation keeps four responsibilities separate:

1. **Decision persistence** owns opportunity state, note, and review timestamp.
2. **Evidence review service** owns recognized taxonomy, deterministic latest
   labels, evidence readiness, and aggregate evaluation.
3. **API schemas and routes** validate input and expose typed contracts without
   duplicating calculation rules.
4. **Frontend review surfaces** render decisions, evidence reviews, queue
   filtering, and evaluation without calculating backend metrics.

The evidence review calculations belong in a focused backend service rather
than expanding `apps/api/app/api/routes.py` with aggregation logic. Frontend
review controls should also be extracted from the already large opportunity
detail component into focused components.

## Data Model And Migration

An Alembic migration after `0005_scan_outcomes.py` adds these columns to
`opportunities`:

- `review_state`: non-null text, indexed, server default `new`;
- `review_note`: nullable text;
- `decision_updated_at`: nullable timezone-aware datetime.

The SQLAlchemy model uses the same application default for newly constructed
rows. Pydantic validates review states; a database-native enum is deliberately
avoided so SQLite smoke tests and PostgreSQL use the same migration shape.

The migration must upgrade existing SQLite and PostgreSQL databases without
data loss and must downgrade by removing the index and three columns. The
existing `labels` table needs no schema migration. The startup
`ensure_sqlite_schema_compatibility` path must add the same columns and index
when an existing local SQLite database is opened without first running
Alembic, matching the compatibility behavior already used for prior additive
schema changes.

## API Contracts

### Opportunity review

`PATCH /api/opportunities/{opportunity_id}/review`

Request:

```json
{
  "review_state": "promising",
  "review_note": "Validate willingness to pay with three maintainers."
}
```

The state is required. The note may be a string or `null`. The response is the
updated `OpportunityOut`.

`OpportunityOut` adds:

- `review_state`;
- `review_note`;
- `decision_updated_at`;
- `evidence_readiness`.

`GET /api/opportunities` accepts an optional validated `review_state` query
parameter. Without it, behavior remains unchanged.

### Evidence review

`POST /api/labels` remains the write endpoint but gains typed validation and a
`LabelOut` response. It returns 404 when the item does not exist.

`GET /api/items/{item_id}/labels` returns all stored reviews newest first,
including legacy unrecognized values, and returns 404 when the item does not
exist.

Evidence items inside `OpportunityOut` add:

- `review_label`: recognized current label or `null`;
- `review_note`: the current recognized label's note or `null`;
- `reviewed_at`: the current recognized label's timestamp or `null`;
- `review_history_count`: count of all stored label rows for the item.

### Evaluation

`GET /api/evaluation` returns the typed evaluation summary defined above. It is
read-only and requires no model runtime or external network access.

### Exports

The existing evidence Markdown, task-pack JSON, and task-pack Markdown outputs
add:

- opportunity review state;
- evidence readiness level, passed checks, and gaps;
- opportunity-local evidence review coverage.

`TaskPackOut` adds `review_state: ReviewState` and
`evidence_readiness: EvidenceReadinessOut`. The JSON representation therefore
uses the exact readiness shape defined above; it does not copy the global
evaluation summary. Evidence and task-pack Markdown render a `Decision Context`
section containing the review state, readiness level, four check results,
opportunity-local human review coverage, and deterministic gaps.

The local opportunity review note and evidence review notes are excluded from
exports by default. This avoids copying local annotations into artifacts that
may be shared with agents or reviewers. Existing author, credential, raw
payload, safe-URL, and prompt-injection boundaries remain unchanged.

## Frontend Experience

### Dashboard decision queue

The dashboard adds:

- one count chip for each review state;
- an `All states` filter plus the six state values;
- a state badge on every opportunity row/card;
- evidence-readiness level alongside the existing score and signal count.

Filtering operates on the already fetched opportunity list for immediate local
interaction. The API filter remains available for CLI and future agent use.
Changing the filter never changes persisted state.

### Opportunity detail

A focused Decision panel near the title contains:

- state select;
- local review-note textarea marked "Excluded from exports";
- save button;
- last decision-update timestamp;
- clear copy that only the operator can make a build decision.

The panel uses a mutation and refetches the opportunity after a successful save.
It does not use optimistic updates, so the UI never shows an unpersisted
decision as saved.

The evidence trail adds an evidence-readiness card with the four named checks.
Each evidence item adds a compact label selector, optional note field, save
action, latest label, and history count. Saving appends a review and refetches
the opportunity and evaluation queries.

### Evaluation page

A new `/evaluation` page and navigation entry show:

- total reviewable and reviewed evidence;
- review coverage;
- recognized label counts;
- precision on reviewed positives when defined;
- source and signal-type breakdowns;
- unrecognized legacy-label count;
- the permanent selection-bias and no-recall explanation.

The page has explicit empty states for no generated opportunities and no
reviews. It remains useful without network credentials or an LLM provider.

## Data Flow

1. A fixture or live scan generates opportunities as it does today. New rows
   start in `new` state.
2. Dashboard and detail requests serialize the current decision state and call
   the evidence review service for current labels and readiness.
3. The operator saves an opportunity decision through the review endpoint.
4. The operator reviews evidence; each save appends a `Label` row.
5. React Query invalidates the affected opportunity, opportunity-list, and
   evaluation queries only after a successful response.
6. Evaluation derives current recognized labels at read time and returns honest
   aggregate metrics.
7. Exports render the current decision state and evidence-readiness context but
   omit local review notes.

## Validation And Error Handling

- Unknown opportunity states and new unknown evidence labels return Pydantic
  validation errors with HTTP 422.
- Review notes over their limits return HTTP 422 before database writes.
- Missing opportunities and items return HTTP 404.
- Database writes commit once and refresh the returned row. Failed commits roll
  back and follow the existing API error handling path.
- Frontend mutations show the backend error and keep the last confirmed state
  visible. Success messages appear only after the server response.
- Evaluation handles an empty database, zero recognized labels, and legacy
  labels without division-by-zero errors.
- Unsafe or missing evidence URLs fail the readiness URL check and remain
  filtered by the existing safe-source-URL logic in exports and UI links.
- A current `sensitive_risk` label forces evidence readiness to `weak` and adds
  an explicit gap explaining why.

## Security And Deployment Boundary

Opportunity decisions and evidence labels do not spend credentials or invoke an
external service, so v0.2 does not repurpose `OPERATOR_SCAN_TOKEN` as an account
system. These write endpoints remain part of the single-operator local API and
must not be presented as authenticated or safe for public exposure.

To make the default runtime match that contract:

- Docker Compose publishes the API, web, and database ports on `127.0.0.1`
  rather than every host interface;
- direct web development defaults to localhost rather than explicitly binding
  to `0.0.0.0`;
- deployment and threat-model documentation states that public or team access
  requires authentication and workspace isolation before decision notes or
  labels are exposed;
- local review notes are described as export-excluded annotations, not as data
  protected by an authorization boundary.

Credential-spending source, project-run, source-registry, prompt-enhancement,
and destructive-reset gates keep their existing token behavior.

## Setup And Verification Reliability

The current repository mixes root `.venv` and `apps/api/.venv` expectations,
while the checked-out machine currently has neither frontend dependencies nor
the expected virtual-environment executables. v0.2 standardizes developer
commands on `apps/api/.venv`:

- add `make setup` using `uv sync --project apps/api --extra dev` and the
  Homebrew Node 20 path for `npm ci` in `apps/web`;
- make Python test, lint, migration, smoke, and server commands consistently use
  `apps/api/.venv/bin`;
- update `scripts/doctor.py`, README, and contributor instructions to describe
  the same path;
- preserve the Docker quickstart command and container topology while binding
  published host ports to loopback by default.

Compatible frontend dependencies and the lockfile are updated as needed so
`npm audit --audit-level=moderate` exits successfully. No framework
major-version upgrade is part of this feature.

## Versioning And Documentation

Development version metadata becomes `0.2.0` in the API package, API lockfile,
FastAPI app, web package, and web lockfile root entry. `CHANGELOG.md` gains a
dated v0.2.0 entry describing the decision workbench, evaluation boundaries,
setup repair, and evidence-aware exports.

README, API documentation, model card, roadmap, demo evidence, and architecture
documentation are updated only where behavior or claims change. The README's
"Latest release" link continues to point to the actual published v0.1.3 release
until a separate tag/release action occurs.

The implementation does not push, tag, publish a GitHub release, update tickets,
or mutate a deployed environment.

## Testing Strategy

Implementation follows red-green testing at each boundary.

### Backend

- migration upgrade/downgrade and SQLite schema compatibility;
- default and updated opportunity review state;
- review-state and note validation;
- missing-item and missing-opportunity behavior;
- append-only evidence labels and deterministic latest-label selection;
- legacy unrecognized-label handling;
- evidence-readiness thresholds and sensitive-risk override;
- evaluation counts, coverage, precision denominator, empty state, and
  breakdowns;
- review-state filtering;
- export inclusion of state/readiness and exclusion of local review notes.

### Frontend

- dashboard state counts, filtering, badges, and readiness display;
- decision form initial values, save payload, success, validation, and API error;
- evidence label append flow and query invalidation;
- evaluation populated, empty, undefined-precision, and error states;
- navigation and API request contracts.

### End-to-end proof

The credential-free smoke run will:

1. process the existing fixtures;
2. mark the top opportunity `promising`;
3. review at least one evidence item;
4. assert the evaluation summary changes;
5. export the task pack;
6. verify the decision state and readiness are present while local review notes
   are absent;
7. continue validating the task-pack structure and proof manifest.

### Final verification commands

```bash
make setup
make doctor
make verify
make smoke
python3 scripts/release_check.py
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web audit --audit-level=moderate
git diff --check
```

`make release-check` additionally requires a completely clean worktree. The
existing untracked `.oss-steward/` and
`docs/audits/v0.2-issue-roadmap-2026-06-20.md` must remain untouched, so the
non-clean release-check command above is the authoritative local content and
version gate for this task. A clean-worktree release gate can be run later from
a clean release checkout.

After automated checks pass, the local app will be started and verified through
the in-app Browser surface at desktop and narrow viewport widths. The browser
check covers processing fixtures, dashboard filtering, saving a decision,
labeling evidence, refreshing to prove persistence, viewing evaluation, and
opening decision-aware exports.

## Delivery Boundaries

The work should be delivered in reviewable checkpoints:

1. data model, migration, schemas, and backend tests;
2. evidence review service, evaluation API, exports, and backend tests;
3. dashboard, opportunity review, evidence controls, evaluation page, and web
   tests;
4. setup reliability, smoke proof, version metadata, documentation, and full
   verification.

The existing untracked `.oss-steward/` directory and
`docs/audits/v0.2-issue-roadmap-2026-06-20.md` are user-owned and excluded from
all commits.

## Acceptance Criteria

- Existing and migrated opportunities load as `new` without data loss.
- The operator can persist each allowed opportunity state and a bounded local
  note from the detail page, with clear export-exclusion copy.
- Dashboard counts and filtering reflect persisted states after refresh.
- Evidence review writes are constrained, append-only, and auditable through
  deterministic history.
- Opportunity responses and UI show the current recognized evidence label and
  transparent readiness checks.
- Evaluation reports coverage and precision on reviewed positives without
  claiming recall, F1, global model quality, or market validation.
- A sensitive-risk review forces weak readiness and an actionable explanation.
- Task-pack and evidence exports contain state/readiness context and exclude
  local review notes.
- Default Docker-published ports are loopback-only, and documentation does not
  imply that unauthenticated review writes are safe for public exposure.
- Fixture, live-source, prompt-enhancement, privacy, safe-URL, and proof-manifest
  behavior remain backward compatible.
- `make setup`, `make doctor`, `make verify`, `make smoke`, the non-clean release
  content gate, dependency audit, and `git diff --check` pass.
- Browser verification proves the complete local review loop and persistence.
- API and web development metadata report `0.2.0`; no external release is
  published.
