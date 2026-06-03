# Deployment

## Local Docker

```bash
cp .env.example .env
make up
```

## Vercel Frontend

- Root: `apps/web`
- Build command: `npm run build`
- Environment: `NEXT_PUBLIC_API_BASE_URL`

## Render Or Hugging Face Backend

- Root: `apps/api`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment: `DATABASE_URL`, `AUTHOR_HASH_SALT`, `PUBLIC_SCAN_SOURCES`, `CORS_ALLOWED_ORIGINS`, `DEMO_RESET_TOKEN`, `OPERATOR_SCAN_TOKEN`, connector credentials as needed, and optional `LLM_PROVIDER` runtime variables.

## Hosted Demo Guardrails

For a public read-only demo, start narrow:

```env
PUBLIC_SCAN_SOURCES=fixture,hackernews
CORS_ALLOWED_ORIGINS=https://your-frontend.example,http://localhost:3000,http://127.0.0.1:3000
DEMO_RESET_TOKEN=<long random value>
LLM_PROVIDER=none
```

Keep GitHub, Stack Exchange, and Reddit in trusted internal scan jobs rather
than the unauthenticated public scan API. Review their rate limits, credential
scope, retention behavior, and source terms before running those jobs. If
`DEMO_RESET_TOKEN` is set, destructive fixture resets require the matching
`X-Demo-Reset-Token` header; ordinary non-reset fixture processing remains safe
for browser demos.

ChatGPT/Codex subscriptions are not backend API credentials. For subscription
users, expose task-pack exports and the repo-local
`skills/tasksignal-opportunity-builder` package. Use `OPENAI_API_KEY` only when
the deployment intentionally enables OpenAI API-backed prompt enhancement.

## Supabase Postgres

Enable pgvector:

```sql
create extension if not exists vector;
```

Run Alembic migrations from `apps/api`.

## Scheduled Ingestion

TaskSignal keeps scheduling explicit. Create saved research projects with
manual, hourly, daily, weekly, or custom-hour cadence, then call:

```bash
scripts/tasksignal_cli.py run-due
```

Use cron, GitHub Actions, a worker service, or another scheduler to call
`POST /api/research-projects/run-due`. Store API credentials and
`TASKSIGNAL_OPERATOR_TOKEN` in scheduler secrets, not in the repository.
