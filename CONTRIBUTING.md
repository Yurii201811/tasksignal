# Contributing

TaskSignal is a local-first MVP for discovering evidence-backed software opportunities from public discussion data. Contributions should keep the project useful, transparent, and safe to run from a fresh checkout.

## Development Setup

1. Install the locked API and web development dependencies:

   ```bash
   make setup
   ```

2. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

3. Run the local setup diagnostic:

   ```bash
   make doctor
   ```

4. Start the API and web app in separate terminals:

   ```bash
   cd apps/api
   .venv/bin/uvicorn app.main:app --reload
   ```

   ```bash
   cd apps/web
   npm run dev
   ```

Use `make up` instead when you want the full Docker Compose stack.

## Checks

Run a quick local setup check when starting from a fresh checkout:

```bash
make doctor
```

Run the main checks before opening or merging changes:

```bash
make test
make lint
```

Backend checks live in `apps/api` and use `pytest` plus `ruff`. Frontend checks live in `apps/web` and use the Next.js build plus Vitest.

Check contributed fixtures before opening a PR:

```bash
python3 scripts/check_fixture_redaction.py
```

## Contribution Guidelines

- Keep fixture mode working without paid services or live API credentials.
- Keep fixture records synthetic or heavily sanitized. Do not include real
  usernames, email addresses, API tokens, private/internal URLs, customer data,
  private repository links, or source payloads from unsupported services.
- If a fixture needs an author field to exercise hashing behavior, use an
  obvious placeholder such as `contributor-a`, `edge_hn_user`, or
  `backend_dev`.
- Prefer transparent scoring, evidence links, and explainable rules over opaque automation.
- Do not commit `.env` files, API keys, exported private datasets, local databases, caches, or build output.
- Use public APIs and respect source rate limits and terms.
- Store author hashes rather than raw usernames unless a feature explicitly requires otherwise and documents why.
- Add or update docs when behavior, setup, deployment, data handling, or model assumptions change.

## Pull Request Checklist

- The change has a clear user or developer benefit.
- Fixture demo mode still runs locally.
- Relevant backend and frontend tests pass.
- Documentation is updated when user-facing behavior or setup changes.
- No secrets, credentials, local databases, or generated build artifacts are included.
