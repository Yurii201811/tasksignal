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
- Environment: `DATABASE_URL`, `AUTHOR_HASH_SALT`, `PUBLIC_SCAN_SOURCES`, `DEMO_RESET_TOKEN`, connector credentials as needed.

## Hosted Demo Guardrails

For a public read-only demo, start narrow:

```env
PUBLIC_SCAN_SOURCES=fixture,hackernews
DEMO_RESET_TOKEN=<long random value>
LLM_PROVIDER=none
```

Keep GitHub, Stack Exchange, and Reddit in trusted internal scan jobs rather
than the unauthenticated public scan API. Review their rate limits, credential
scope, retention behavior, and source terms before running those jobs. If
`DEMO_RESET_TOKEN` is set, destructive fixture resets require the matching
`X-Demo-Reset-Token` header; ordinary non-reset fixture processing remains safe
for browser demos.

## Supabase Postgres

Enable pgvector:

```sql
create extension if not exists vector;
```

Run Alembic migrations from `apps/api`.

## Scheduled Ingestion

Use `.github/workflows/scheduled-ingestion.yml` as a safe template. Store API credentials in repository secrets.
