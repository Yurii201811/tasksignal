# TaskSignal Cursor Workspace

This folder makes Cursor work on TaskSignal with the same guardrails as the repo.

## Use Composer 2.5

1. For the broad Codex workspace context, open `../GitHub Project.code-workspace` in Cursor.
2. For a narrower session, open the TaskSignal repo root in Cursor.
3. Open Composer 2.5.
4. Start with `.cursor/plans/tasksignal-ui-ux-polish-composer-2.5.md`.
5. Use Agent mode for execution. Do not ask Composer to create a competing plan.
6. Keep checkpoints after each phase and inspect the diff before continuing.

## Source Of Truth

Read these first:

- `PRODUCT.md`
- `DESIGN.md`
- `README.md`
- `docs/architecture.md`
- `docs/api.md`
- `apps/web/src/components/app-shell.tsx`
- `apps/web/src/components/ui.tsx`
- `apps/web/src/app/globals.css`
- `apps/web/src/features/*.tsx`

## Verification

Frontend checks need a modern Node runtime:

```bash
cd apps/web
npm test
npm run build
```

For full release readiness:

```bash
python3 scripts/release_check.py
```

Use browser verification for UI changes. Check desktop plus 320, 375, 414, and 768 px widths.
