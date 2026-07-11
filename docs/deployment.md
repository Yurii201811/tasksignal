# Deployment

TaskSignal v1 supports one local operator. The hosted configuration is a
protected single-operator preview, not a team or production service.

## Supported Runtime Boundary

- Python 3.11 through 3.14 on macOS and Linux.
- Windows through WSL only for v1; native Windows is not a release target.
- SQLite by default in packaged local mode.
- PostgreSQL for source-checkout, Compose, and explicitly managed hosted
  deployments.
- Stdio MCP only. HTTP MCP and OAuth are not supported.
- Full Next.js UI from a source checkout or a versioned container image when one
  is published. The Python wheel does not contain Node.js or the web app.

The repository includes build and CI configuration for this boundary. Treat a
configured job as intent, not passing evidence; record the actual run before a
release claim.

## Packaged Local Mode

The `tasksignal` distribution contains the FastAPI app, CLI, public fixtures, and
Alembic migrations. This documentation does not claim that it is already
published to PyPI. Install it from the source checkout while validating a
candidate:

```bash
uv tool install './apps/api'
# Add stdio MCP only when needed:
uv tool install './apps/api[mcp]'
```

Initialize, migrate, diagnose, and serve:

```bash
tasksignal init
tasksignal migrate
tasksignal doctor
tasksignal serve
```

`init` creates platform-specific data/config paths and a permission-`0600`
secret config without printing generated values. Environment variables override
file values. For an isolated or portable test, set:

```bash
export TASKSIGNAL_DATA_DIR=/absolute/path/to/tasksignal-data
export TASKSIGNAL_CONFIG_FILE=/absolute/path/to/tasksignal-config.env
```

`migrate` reads Alembic revisions from the installed package. A stale SQLite
database is copied to a timestamped permission-`0600` backup before upgrade.
Unknown revisions and nonempty unversioned schemas are refused. Inspect and
fingerprint such a schema, compare it with a named historical revision, then use
the explicit acknowledgement-gated stamp workflow only when that comparison is
complete.

`serve` sets table auto-creation off, refuses a schema that is not at the
packaged head, and accepts only `localhost`, `127.0.0.1`, or `::1`. Use the
noun-first CLI groups against the local service:

```text
tasksignal projects ...
tasksignal runs ...
tasksignal opportunities ...
tasksignal evidence ...
tasksignal packets ...
tasksignal sessions ...
```

The API URL precedence is `--api-url`, `TASKSIGNAL_API_URL`, legacy
`TASKSIGNAL_API_BASE`, then `http://127.0.0.1:8000`. Plain HTTP is accepted only
for exact loopback hosts; remote API targets require HTTPS.

## Packaged MCP

Install the `mcp` extra, initialize and migrate, then run:

```bash
tasksignal mcp
```

Keep stdio attached directly to the local MCP client. Do not put it behind a
network bridge. Reads are immediate; writes require explicit UI or interactive-
TTY approval for that process. A 30-second heartbeat renews a 60-second lease,
and configured-AI packet generation requires separate capability approval.

The MCP process and API must point to the same local database/config. The raw
session secret remains in MCP process memory and is erased on shutdown; only its
hash is stored.

## Source Checkout

```bash
make setup
cp .env.example .env
make doctor
make dev
```

`make dev` prints the API and web commands; run them in separate terminals. The
native API loads `apps/api/.env`, while the web app uses
`apps/web/.env.local`. The root `.env` is repository-tooling input and is not
implicitly loaded by either process.

Use `make setup-ml` only when the optional local semantic-model stack is wanted.
The `ml` extra is outside the base+MCP audited dependency surface and must be
assessed separately. That scope boundary does not imply a known vulnerability.

## Local Docker Compose

```bash
cp .env.example .env
make migrate
make up
```

Compose publishes PostgreSQL, FastAPI, and Next.js on `127.0.0.1` by default.
`make migrate` rebuilds the API image so current packaged migrations are present,
then upgrades the explicit Compose PostgreSQL URL before serving.

Table auto-creation can create missing tables in local development but does not
migrate an existing PostgreSQL schema. Do not use it as an upgrade mechanism. A
legacy unversioned volume needs inspection and an explicit stamp/migration plan;
do not delete it automatically.

The local workspace profile is one singleton row. Decisions, labels, Discourse
authorization, packet creation, and agent sessions do not become safe multi-user
operations merely because the stack is containerized.

## Versioned Container Images

The repository keeps the Next.js UI available through source checkout and
container builds. A release can publish a versioned Docker/GHCR image only after
the image, Python artifact, GitHub release, CI evidence, proof manifest, and
migration record are pinned to the same commit SHA.

Until such an image is published for the target version, build from the verified
source checkout instead of treating an unversioned or `latest` image as release
evidence.

## Hosted Single-Operator Preview

The preview topology can use a Vercel Next.js project, a separately deployed
FastAPI backend, and a managed PostgreSQL database. Keep health and CORS
preflight public, and set:

```env
AUTO_CREATE_TABLES=false
PUBLIC_SCAN_SOURCES=fixture
CORS_ALLOWED_ORIGINS=https://your-exact-frontend.example
AUTHOR_HASH_SALT=<long-random-value>
DEMO_RESET_TOKEN=<different-long-random-value>
OPERATOR_SCAN_TOKEN=<another-long-random-value>
REQUIRE_OPERATOR_TOKEN_FOR_ALL_API=true
REQUIRE_OPERATOR_TOKEN_FOR_WRITES=true
LLM_PROVIDER=none
```

The frontend sends `X-Operator-Scan-Token` as a header for protected JSON and
downloads; never place it in a URL. One shared operator token is not user
authentication. Do not invite multiple users, store private sources, or promise
durability/availability without tenancy, retention, deletion, and operational
controls.

Keep the preview on fixtures unless the operator has reviewed each connector's
terms, quotas, credentials, and retained fields. Discourse additionally requires
a saved source and human confirmation for one exact HTTPS origin. Source-host
authorization is intentionally unavailable to MCP.

Run `alembic upgrade head` outside request startup against a verified migration
URL. Use a pooled URL for request traffic only when the provider recommends it.
An unknown or unversioned hosted schema requires explicit inspection and
stamping; do not let application startup guess its lineage.

### Vercel Frontend

- Project root: `apps/web`
- Install command: `npm ci`
- Build command: `npm run build`
- Environment: `NEXT_PUBLIC_API_BASE_URL=https://your-api.example`

### Vercel API Packaging

- Source root: `apps/api`
- Prepare command: `scripts/prepare_vercel_api.sh`
- Generated deployment root: `.vercel-api` (gitignored)
- Entrypoint: `app.main:app`

The prepare script limits the upload to runtime code, locked dependencies,
configuration, migrations, and canonical public fixtures. It must not copy local
environment files, tests, SQLite databases, frontend files, or private exports.
Keep migrations outside serverless request startup.

### Optional Render Backend

The repository-root `render.yaml` can supply PostgreSQL through `DATABASE_URL`.
TaskSignal normalizes provider PostgreSQL URLs to the installed psycopg3 driver.
Confirm current account, billing, quota, and region requirements directly with
the provider before deployment; do not infer them from this repository.

### Supabase or Other PostgreSQL

Enable pgvector when the selected processing path requires it:

```sql
create extension if not exists vector;
```

Set the exact hosted `DATABASE_URL` in `apps/api/.env` or the current shell,
verify the target, then run `make migrate-native`. Never point a migration at an
unverified shared database.

## Scheduled Research

TaskSignal stores cadence and `next_run_at` but does not run a hidden scheduler
inside the web process. Use an explicit local cron, GitHub Actions job, worker,
or operator invocation to call:

```text
POST /api/v1/research-projects/run-due
```

Store connector credentials and `TASKSIGNAL_OPERATOR_TOKEN` in the scheduler's
secret store. Observe each source's terms, rate limits, `Retry-After`, and
retention rules. `not observed this run` must never be converted into automatic
deletion or resolution.

## Model Configuration

No paid model is required. Deterministic build documents and fallback vectors are
the authoritative base path.

Configured enhancement uses either `LLM_PROVIDER=openai` with `OPENAI_API_KEY`,
or `LLM_PROVIDER=ollama` with a reachable local Ollama server. It can add
validated `enhanced/` packet variants but cannot replace deterministic originals.
In the UI/API, configured-AI calls require the operator token. In MCP, they also
require the separately selected `use_configured_ai` capability.

ChatGPT or Codex subscriptions are not backend API credentials. TaskSignal does
not create GitHub issues automatically; `github-issue.md` remains a local draft.
