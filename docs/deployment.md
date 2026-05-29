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
- Environment: `DATABASE_URL`, `AUTHOR_HASH_SALT`, connector credentials as needed.

## Supabase Postgres

Enable pgvector:

```sql
create extension if not exists vector;
```

Run Alembic migrations from `apps/api`.

## Scheduled Ingestion

Use `.github/workflows/scheduled-ingestion.yml` as a safe template. Store API credentials in repository secrets.

