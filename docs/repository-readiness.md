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

## Public Signal Gap

Current public evidence is mostly maintainer-created: release hygiene, tests, screenshots, documentation, issues, and a reproducible fixture demo. That is enough to show seriousness, but it is not the same as adoption.

The live-source path now records scan outcome counts and guidance, so a public
scan that saves records but produces zero opportunities is still auditable. This
improves product maturity, but it does not remove the need for independent
tester feedback or better source/query examples.

The next material readiness improvements are:

1. Get at least three independent testers to run the fixture demo and file feedback issues.
1. Link any public mentions, demos, or user feedback in `docs/codex-for-oss-application.md`.
1. Keep the release-readiness workflow green before every public release.
1. Close at least one security/privacy hardening issue with tests.
1. Add a hosted read-only demo only after data retention, connector limits, and deployment credentials are reviewed.
