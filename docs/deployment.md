# Deployment

## Local Docker

```bash
cp .env.example .env
make migrate
make up
```

Docker Compose publishes PostgreSQL, FastAPI, and Next.js on `127.0.0.1` by default. Opportunity decisions and evidence labels are unauthenticated local-operator writes. Do not expose them publicly or to a team until authentication, workspace isolation, retention, and deletion controls exist.

`AUTO_CREATE_TABLES=true` creates missing tables but does not migrate an existing PostgreSQL schema. `make migrate` runs Alembic inside the Compose API service, rebuilds that image so the current migrations are present, and uses the explicit Compose PostgreSQL URL. Run it before `make up` when upgrading a migration-managed Compose database.

The repository-root `.env` is not loaded by the native API or by
`make migrate-native`, and it does not select the Compose migration database;
the Compose service definition supplies its PostgreSQL URL. For a native or
externally hosted database, put the intended `DATABASE_URL` in `apps/api/.env`
(or export it in that terminal), then run `make migrate-native`. That target
runs from `apps/api`, where the API settings loader reads `apps/api/.env`.
Verify the target URL before migrating production or another shared database.

A legacy unversioned Compose volume requires schema inspection and an explicit
Alembic stamp/migration plan; do not delete the volume automatically.

The default deployment target is a single local operator. Configure the local
workspace from Settings or with `scripts/tasksignal_cli.py configure-workspace`;
do not add public multi-user access until authentication, tenant isolation,
retention, and admin deletion paths are designed.

## Hosted Single-Operator Preview

The card-free preview topology uses two Vercel projects and a Neon Free
PostgreSQL database:

- frontend project root: `apps/web`;
- API source root: `apps/api`, packaged by `scripts/prepare_vercel_api.sh` into
  the gitignored `.vercel-api` deployment root so only runtime code, locked
  dependencies, configuration, and the canonical public fixtures enter the
  upload boundary;
- database: Neon Free PostgreSQL through the Vercel Marketplace integration.

Health and CORS preflight stay public, while
`REQUIRE_OPERATOR_TOKEN_FOR_ALL_API=true` requires the configured
`OPERATOR_SCAN_TOKEN` as `X-Operator-Scan-Token` for every `/api/` read, write,
and Markdown export. Enter the same token in the frontend unlock banner or
Settings page; it stays in that browser's local storage. The shared API client
adds it as a header, including protected downloads, without placing it in URLs.

Provision Neon for the API project, run `alembic upgrade head` once against its
unpooled migration URL, provide a long random `OPERATOR_SCAN_TOKEN`, and keep
`PUBLIC_SCAN_SOURCES=fixture` for the preview. Pin the API function to the same
region as the provisioned database (`iad1` for the current Vercel Marketplace
resource); its Hobby duration is configured to the 60-second maximum for
fixture processing.

Neon Free currently has no time limit or card requirement, but its storage,
compute, and transfer quotas still make this a disposable personal preview, not
a durable multi-user production system. Delete the database and API project
when the evaluation window ends.

## Vercel Frontend

- Root: `apps/web`
- Install command: `npm ci`
- Build command: `npm run build`
- Environment: `NEXT_PUBLIC_API_BASE_URL=https://tasksignal-api-yurii201811.vercel.app`
- Stable origin: `https://tasksignal-yurii201811.vercel.app`

## Vercel API and Neon Database

- Prepare command: `scripts/prepare_vercel_api.sh`
- Deployment root: `.vercel-api` (generated and gitignored)
- Source root: `apps/api`
- Framework preset: FastAPI
- Entrypoint: `app.main:app`
- Function region: Washington, D.C. (`iad1`), matching the current Neon resource
- Environment: Neon pooled `DATABASE_URL` plus the hosted guardrails below

Vercel installs the API package from the copied `pyproject.toml` and `uv.lock`.
The prepare script recreates `.vercel-api` before every deployment and copies
only the runtime package, deployment manifests, and public fixtures. It never
copies local environment files, tests, SQLite databases, frontend files, or
other repository content. Keep migrations outside request startup: use the
Neon unpooled URL for `alembic upgrade head`, then use the pooled URL in the
serverless API.

## Optional Render Backend

Use the repository-root `render.yaml` so repo-level fixtures stay available.
Render supplies PostgreSQL through `DATABASE_URL`; TaskSignal normalizes the
provider URL to the installed psycopg3 driver. The hosted core intentionally
omits the optional ML extra and uses deterministic embeddings/clustering. As of
2026-07-10, Render account setup required a payment card even for this free
Blueprint, so it is not the primary card-free preview path.

## Hosted Demo Guardrails

For a protected single-operator preview, start narrow:

```env
AUTO_CREATE_TABLES=false
PUBLIC_SCAN_SOURCES=fixture
CORS_ALLOWED_ORIGINS=https://tasksignal-yurii201811.vercel.app
AUTHOR_HASH_SALT=<long random value>
DEMO_RESET_TOKEN=<long random value>
OPERATOR_SCAN_TOKEN=<different long random value>
REQUIRE_OPERATOR_TOKEN_FOR_ALL_API=true
REQUIRE_OPERATOR_TOKEN_FOR_WRITES=true
LLM_PROVIDER=none
```

Keep GitHub, Stack Exchange, and Reddit in trusted internal scan jobs rather
than the browser preview. Review their rate limits, credential
scope, retention behavior, and source terms before running those jobs. If
`DEMO_RESET_TOKEN` is set, destructive fixture resets require the matching
`X-Demo-Reset-Token` header. Hosted API protection requires the operator token
for reads, exports, and every mutating route, including ordinary fixture
processing, decisions, evidence reviews, workspace changes, and project
creation.

ChatGPT/Codex subscriptions are not backend API credentials. For subscription
users, expose task-pack exports and the repo-local
`skills/tasksignal-opportunity-builder` package. Use `OPENAI_API_KEY` only when
the deployment intentionally enables OpenAI API-backed prompt enhancement.

## Supabase Postgres

Enable pgvector:

```sql
create extension if not exists vector;
```

Set the hosted `DATABASE_URL` in `apps/api/.env` or the current shell, verify it,
then run `make migrate-native` from the repository root.

## Scheduled Ingestion

TaskSignal keeps scheduling explicit. Create saved research projects with
manual, hourly, daily, weekly, or custom-hour cadence, then call:

```bash
scripts/tasksignal_cli.py run-due
```

Use cron, GitHub Actions, a worker service, or another scheduler to call
`POST /api/research-projects/run-due`. Store API credentials and
`TASKSIGNAL_OPERATOR_TOKEN` in scheduler secrets, not in the repository.
