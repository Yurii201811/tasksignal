# UX Audit

## UX Direction

Source file: `DESIGN.md`

TaskSignal's design system is restrained and appropriate for a research tool: cool near-white background, tinted panels, deep text, muted slate, teal primary actions, amber attention states, dense labels, left navigation on desktop, single-column mobile flow, and cards for bounded summaries.

The current UI largely follows the product brief: it feels like an operator workbench, not a marketing landing page.

## Strong UX Patterns

- The app starts with usable product surfaces rather than a landing page.
- Desktop navigation is predictable and includes Dashboard, Projects, Sources, Scans, Search, and Integrations.
- Dashboard frames the "first useful run" as a checklist tied to live readiness state.
- Fixture mode and live scan are separated clearly.
- Scan detail explains completed-without-opportunities and failed-scan states.
- Opportunity detail exposes evidence, source mix, score formula, raw factors, weighted impact, and exports.
- Prompt view checks whether evidence, ranking rationale, and privacy constraints are present.
- Integrations page explains credentialed scans and operator token gating.

## Main UX Frictions

### 1. Enhancement Button Can Fail Without Local Token Context

Opportunity detail has an "Enhance Prompt" action, but the web helper does not send the operator token required by the API. Users may see a 403 without knowing they need the token/runtime configuration.

Recommendation: add a readiness card or disabled state explaining provider and token requirements. Reuse the operator token from local storage only if that storage model remains accepted for local mode.

### 2. Dashboard Is Demo-Strong But Decision-Light

The dashboard is excellent for first-run proof. It is less strong for ongoing decisions:

- no scan-to-scan comparison
- no "new since last run" summary
- no opportunity aging or status
- no decision log: investigate, reject, build, archive

Recommendation: add a "research queue" layer in v0.2.

### 3. Search Stops At Evidence Items

Semantic search helps find evidence records but does not connect those hits back to opportunities, clusters, or task packs.

Recommendation: show "related opportunities" or "create review set from these hits."

### 4. Integrations Page Mixes Workspace And Runtime Setup

Settings/Integrations includes local owner, default workflow, operator token, readiness, and integration tests. This is practical but dense.

Recommendation: split information architecture into:

- Workspace defaults
- Source integrations
- Runtime and agent handoff
- Security gates

This can still live on one page if tabs or anchors are used.

### 5. Project Workflow Needs Outcome Memory

Research projects store run count and last scan status, but users need stronger review memory:

- what changed since previous run
- what opportunity was exported
- which ideas were rejected
- which queries are producing weak signals

Recommendation: add project-level notes/status and scan comparison.

## Route-Level Recommendations

### `/dashboard`

Keep first-run checklist. Add "Last useful result" and "Next best action" based on readiness and latest scan outcome. Add clearer handling when public scan sources are configured as none.

### `/projects`

Add project status labels: Draft, Watching, Needs Review, Promising, Paused. Add "last useful opportunity" and "query quality" indicators.

### `/scans`

Add filters by source/status/project. Add "zero opportunities" as a first-class status, not just completed.

### `/scans/[id]`

Add links to generated opportunities from that scan. Today the detail records counts but does not give a direct path to scan-specific outputs.

### `/search`

Add opportunity/cluster results, filters by source/date/signal type, and "save as project query" action.

### `/settings`

Make token/runtime requirements more explicit for actions that need them. Consider session-only token storage for hosted mode.

### `/opportunities/[id]`

Add reviewer actions: Mark as promising, needs more evidence, duplicate, too generic, invalid. These actions can feed evaluation data.

### `/opportunities/[id]/prompt`

Add export variants:

- Codex implementation prompt
- PRD
- GitHub issue draft
- validation interview plan
- evidence-only packet

## Accessibility And Responsiveness Notes

Observed source patterns are generally healthy:

- semantic links/buttons
- visible focus classes
- skip link
- mobile navigation
- table shells for overflow
- icons from `lucide-react`

Next audit should include browser-based visual and keyboard verification. This audit did not run live Browser/Chrome UI inspection.
