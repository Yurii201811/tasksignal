# Repository Readiness

This checklist documents the public-repository assumptions for TaskSignal.

## Public Release Posture

- The fixture demo runs without paid API keys.
- `.env.example` documents optional credentials without storing secrets.
- `.gitignore` excludes `.env`, local databases, caches, build output, and dependency directories.
- The README links to product, architecture, API, deployment, ethics, model, contribution, and security documentation.
- GitHub Actions run backend lint/tests and frontend build/tests.
- Scheduled ingestion is disabled by default and requires repository secrets before live use.

## Before Making The Repo Public

1. Confirm the working tree is clean except for intended documentation or code changes.
1. Run a secret sweep across tracked files.
1. Run backend and frontend checks.
1. Confirm no local databases or generated artifacts are tracked.
1. Push to the intended GitHub owner account.
1. Set repository visibility to public only after credentials and generated files are excluded.

## Suggested Repository Description

AI-assisted problem discovery engine that turns public developer complaints into evidence-backed software opportunities and Codex-ready MVP prompts.

## Suggested Topics

`ai`, `product-discovery`, `fastapi`, `nextjs`, `postgresql`, `pgvector`, `machine-learning`, `developer-tools`, `portfolio-project`
