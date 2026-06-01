# TaskSignal UI And UX Polish Plan For Cursor Composer 2.5

Use this file as the main Composer 2.5 instruction. Work in:

the TaskSignal repo root

## Ready-To-Paste Composer 2.5 Prompt

Use Composer 2.5 as the executor. Do not create a competing plan. Follow this Codex-authored plan phase by phase in Agent mode. Before each phase, restate the phase you are executing, the files you will touch, and the checks you will run. Then implement only that phase.

You are polishing TaskSignal, a local-first evidence-backed problem discovery app. Apply the repo-local Cursor rules in `.cursor/rules/tasksignal-project.mdc` and `.cursor/rules/tasksignal-ui-ux-polish.mdc`.

Read first:

- `PRODUCT.md`
- `DESIGN.md`
- `README.md`
- `docs/architecture.md`
- `docs/api.md`
- `apps/web/src/components/app-shell.tsx`
- `apps/web/src/components/ui.tsx`
- `apps/web/src/app/globals.css`
- `apps/web/src/features/dashboard.tsx`
- `apps/web/src/features/opportunity-detail.tsx`
- `apps/web/src/features/prompt-view.tsx`
- `apps/web/src/features/scans.tsx`
- `apps/web/src/features/sources.tsx`
- `apps/web/src/features/search.tsx`

Goal: make TaskSignal feel like a serious, polished, research-grade product UI and a stronger open-source application candidate. Preserve the actual product workflow: process fixture data, review ranked opportunities, inspect evidence and scoring rationale, run transparent live scans, and export a Codex-ready prompt. Do not invent adoption proof, usage metrics, customers, testimonials, or claims. Do not add dependencies or change backend API shapes unless absolutely necessary and explained first.

Use Cursor well:

- Use Codebase search to find shared UI patterns and all route entry points.
- Use Agent mode one phase at a time.
- Do not switch into Plan mode unless the human explicitly asks for a new plan.
- Keep Cursor checkpoints after each phase.
- Use terminal checks after each meaningful implementation slice.
- Inspect the diff before moving to the next phase.
- Use browser preview for the real app, not only code inspection.
- Run the TaskSignal UI Verifier agent before final commit.

## Working Assumptions

- Register: product.
- Audience: developers, indie hackers, founders, product managers, and maintainers evaluating public workflow pain.
- Use case: process demo or live public-source data, understand why an opportunity ranks highly, and export an evidence-preserving Codex prompt.
- Tone: technical, utilitarian, research-grade.
- Quality bar: flagship portfolio MVP for an OSS program application. It should look credible, not flashy.

## Current Repo-Grounded Diagnosis

These are the current friction points visible from the source:

- Shared UI primitives are too thin. `Card`, `Badge`, `ButtonLink`, and `ScoreBar` do not yet cover button variants, control states, error/success/loading states, table states, empty states, or consistent focus handling.
- The app shell has no active navigation state and mobile navigation omits Home. It works, but it does not yet feel like a mature product shell.
- `globals.css` and chart colors use hard-coded raw colors. The design system exists in docs, but implementation should consolidate tokens and use them consistently.
- The landing page is helpful, but it leans toward a marketing hero. For this app, the first screen should make the actual workflow and proof path more visible.
- The dashboard has the right ingredients, but fixture processing, live scanning, latest scan status, metrics, ranked table, and charts need clearer hierarchy and stronger empty/loading/error states.
- Opportunity detail has strong content, but evidence, attribution, scoring explanation, and export actions can be arranged more like a research review workspace.
- Current evidence blockquotes use a colored left border wider than 1px. Replace that side-stripe pattern with a full evidence surface, quote mark, tint, or structured excerpt treatment.
- The scoring driver area is visually close to a nested card. Rework it as a section, divider, list, or table inside the scoring panel.
- Prompt export works, but copy/download states can be more confident and auditable.
- Scans, Sources, and Search need the same mature page header, table/list treatment, loading, empty, error, and success vocabulary as the dashboard.

## Non-Negotiables

- Keep fixture mode working without credentials.
- Keep live scan behavior transparent and credential-honest.
- Preserve privacy defaults and source attribution.
- Do not add outreach, scraping, spam, or profiling language.
- Do not fabricate external signals or metrics.
- Do not add new dependencies without approval.
- Do not remove routes.
- Do not bury evidence behind decoration.
- Do not create nested cards.
- Do not use gradient text, fake chrome, decorative glass, side-stripe accents, or generic identical feature-card filler.
- Do not make broad backend changes for visual polish.

## Phase 0: Preflight And Baseline

Use read-only inspection to confirm the existing frontend before edits. Do not generate a new plan.

1. Confirm git status is clean or identify unrelated changes.
2. Read the files listed in the prompt.
3. Map routes:
   - `/`
   - `/dashboard`
   - `/opportunities/[id]`
   - `/opportunities/[id]/prompt`
   - `/scans`
   - `/sources`
   - `/search`
   - `/settings`
4. Identify existing API data shapes from `apps/web/src/lib/types.ts` and `apps/web/src/lib/api.ts`.
5. Record baseline visual issues from code and browser.
6. Decide whether the first implementation slice can stay frontend-only. Default: yes.

Acceptance:

- Composer reports inspected files.
- Composer states planned changed files before editing.
- No backend or dependency changes are proposed unless justified.

## Phase 1: Design System Consolidation

Target files:

- `apps/web/src/app/globals.css`
- `apps/web/tailwind.config.ts`
- `apps/web/src/components/ui.tsx`

Implement:

1. Add CSS custom properties for TaskSignal colors, focus ring, shadows, surfaces, semantic states, and chart colors.
2. Reference tokens from Tailwind where useful, without breaking existing classes.
3. Make `Card` support purposeful variants only: default, muted, success, warning, danger, and compact. Keep radius at 8px or less.
4. Add shared primitives as needed:
   - `Button`
   - `IconButton` if a real icon-only control appears
   - `Input`
   - `Select`
   - `PageHeader`
   - `StateMessage`
   - `EmptyState`
   - `TableShell`
   - `MetricTile`
5. Ensure controls include hover, focus-visible, active, disabled, loading, error, and success states where relevant.
6. Add reduced-motion-safe transitions.
7. Keep color restrained. Teal should signal primary action, selection, and progress. Amber should signal attention or scoring, not decoration.

Acceptance:

- Existing screens still render.
- Shared primitives reduce repeated class strings.
- No new visual language conflicts with `DESIGN.md`.
- No pure black or pure white is introduced as a new design decision.

## Phase 2: App Shell And Navigation

Target files:

- `apps/web/src/components/app-shell.tsx`
- Possibly `apps/web/src/components/ui.tsx`

Implement:

1. Add active route state using Next navigation APIs.
2. Add a skip-to-content link.
3. Improve desktop nav scanability with current route treatment, stable icon sizing, and restrained hover/focus states.
4. Improve mobile navigation so all key routes are reachable without cramped labels.
5. Keep the shell product-like and calm. No marketing header treatment.
6. Ensure nav text never wraps awkwardly or overflows at 320 px.

Acceptance:

- Current route is obvious.
- Keyboard users can skip navigation.
- Mobile nav works at 320, 375, and 414 px.
- No page-level horizontal scroll.

## Phase 3: Dashboard Workflow Polish

Target files:

- `apps/web/src/features/dashboard.tsx`
- Shared primitives from `ui.tsx`

Implement:

1. Rework the page header around the actual workflow:
   - primary action: process demo data
   - secondary workflow: run a live source scan
   - context: local-first, evidence-backed, no paid LLM required
2. Separate fixture demo and live scan controls clearly without making two competing heroes.
3. Improve live scan form:
   - use shared `Select`, `Input`, and `Button`
   - show source query defaults clearly
   - keep limit constrained and understandable
   - show loading, success, and error feedback near the form
4. Improve metric tiles:
   - use consistent `MetricTile`
   - show values only from real API data
   - no fake trends or made-up deltas
5. Improve ranked opportunities table:
   - stronger score visual, but no fake certainty
   - clear top source attribution
   - clear action affordance
   - skeleton/loading row
   - useful empty state that points to Process demo data
   - table scroll contained inside the table shell
6. Improve chart panels:
   - tokenized colors
   - accessible tooltips where possible
   - useful empty states
   - no chart decoration when data is absent
7. Keep the screen dense but breathable.

Acceptance:

- A first-time reviewer immediately understands what to click.
- Running fixtures, seeing opportunities, and opening one remains obvious.
- Live scan status and errors stay visible and auditable.
- Empty dashboard state is helpful, not blank.

## Phase 4: Opportunity Detail Research Workspace

Target files:

- `apps/web/src/features/opportunity-detail.tsx`
- Shared primitives from `ui.tsx`

Implement:

1. Improve the top section:
   - back link
   - title
   - problem statement
   - score
   - action group for View Codex Prompt, Export Markdown, Regenerate
2. Make the score breakdown more inspectable:
   - retain formula logic and weights
   - show raw score and weighted impact clearly
   - show competition penalty as a penalty
   - keep explanation visible
3. Replace nested-card-like score driver treatment with a section, list, or compact table.
4. Rework evidence items:
   - source badge
   - signal type
   - source link
   - title
   - pain/task/buying mini scores
   - evidence spans or body excerpt
   - no colored left side stripe wider than 1px
5. Add a small privacy/source note if it can be true from the data shown.
6. Ensure long excerpts, URLs, and titles wrap cleanly.

Acceptance:

- Evidence feels like the center of the product.
- The ranking rationale is understandable without pretending to be more precise than it is.
- Source attribution is easy to find.
- No nested cards or side-stripe blockquotes remain.

## Phase 5: Prompt Export Polish

Target files:

- `apps/web/src/features/prompt-view.tsx`

Implement:

1. Improve action states:
   - copy disabled when unavailable
   - copied success feedback
   - download action clear
   - loading and error states with recovery path
2. Make the prompt preview readable for long Markdown:
   - stable max width
   - code/pre wrapping behavior
   - no overflow on mobile
3. Preserve prompt content exactly. Do not paraphrase generated prompt text in UI code.
4. Keep privacy constraints visible in supporting copy if true.

Acceptance:

- Copy/download workflow feels reliable.
- Prompt preview is readable on desktop and mobile.
- No generated prompt content is altered by the UI.

## Phase 6: Secondary Screen Consistency

Target files:

- `apps/web/src/features/scans.tsx`
- `apps/web/src/features/sources.tsx`
- `apps/web/src/features/search.tsx`
- Possibly settings route if it contains visible UI

Implement:

1. Apply the same `PageHeader`, `Button`, `TableShell`, `StateMessage`, and empty-state vocabulary.
2. Scans:
   - clear status treatment
   - query/source/time columns scan well
   - loading, empty, and error states
   - run public GitHub scan button state is clear
3. Sources:
   - show fixture and live connectors with credential honesty
   - avoid implying credentials are stored in the browser
   - make enabled/disabled status obvious
4. Search:
   - loading, empty, error, and result states
   - result cards should be evidence records, not marketing cards
   - show similarity as a computed value, not a success claim
5. Keep each screen consistent, but do not make every page the same layout.

Acceptance:

- Secondary routes feel like the same mature app.
- Each route has useful empty and loading states.
- No route becomes decorative filler.

## Phase 7: Responsive, Accessibility, And Interaction QA

Use browser verification. Check:

- 320 px
- 375 px
- 414 px
- 768 px
- 1024 px
- desktop width

Checklist:

- No page-level horizontal scroll.
- Tables scroll inside their own wrappers only.
- Touch targets are at least 44 px on mobile.
- Focus-visible states are obvious.
- Buttons, links, badges, table cells, chart containers, and prompt content do not overflow.
- Loading, empty, error, and success states are visible.
- Reduced motion is respected.
- Keyboard tab order is logical.
- Console has no new warnings or errors.

## Phase 8: Test And Build

Run:

```bash
cd apps/web
npm test
npm run build
```

If docs, repo metadata, or public evidence changed, also run:

```bash
python3 scripts/release_check.py
```

If a command fails because of environment setup, capture the exact failure and provide a manual verification path.

## Phase 9: Final Review And Commit

Before commit:

1. Inspect the full git diff.
2. Run the `TaskSignal UI Verifier` agent from `.cursor/agents/tasksignal-ui-verifier.md`.
3. Confirm no secrets, `.env` values, local paths, generated caches, or screenshots outside intended docs were added.
4. Confirm no invented external signals were added.
5. Confirm no unrelated backend behavior changed.
6. Summarize:
   - changed files
   - UI/UX improvements
   - checks run
   - browser widths verified
   - remaining risks

Suggested commit message:

```text
Polish TaskSignal product UI and evidence workflow
```

## Expected Edit Surface

Likely changed:

- `apps/web/src/components/ui.tsx`
- `apps/web/src/components/app-shell.tsx`
- `apps/web/src/app/globals.css`
- `apps/web/tailwind.config.ts`
- `apps/web/src/features/dashboard.tsx`
- `apps/web/src/features/opportunity-detail.tsx`
- `apps/web/src/features/prompt-view.tsx`
- `apps/web/src/features/scans.tsx`
- `apps/web/src/features/sources.tsx`
- `apps/web/src/features/search.tsx`

Usually unchanged:

- Backend services
- Database models
- API response shapes
- Public docs
- CI workflows
- Release metadata

Only edit the usually unchanged files if the UI polish exposes a real mismatch that cannot be solved locally in the frontend.
