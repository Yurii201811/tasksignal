# TaskSignal - AI Problem Discovery Engine

From Reddit/forum complaints → evidence-backed project ideas → build-ready Codex prompts.

TaskSignal is an AI-assisted engine that mines public developer and community discussions, detects concrete repetitive tasks people complain about, clusters similar pain signals, scores software opportunities, and generates Codex-ready MVP prompts.

![TaskSignal dashboard after processing demo data](docs/images/dashboard-browser-verified.png)

## Project Status

TaskSignal is a portfolio-ready MVP built by Yurii Bakurov. It is designed to run locally with fixture data out of the box, then run repeatable API-backed research workflows for supported public sources when credentials are provided.

Current public posture: TaskSignal is an early public application repository, not a widely adopted package. Its strongest evidence today is reproducibility, release hygiene, CI, security/privacy documentation, contributor issues, and a browser-verified demo flow. See the [demo evidence snapshot](docs/demo-evidence.md) and [Codex for OSS evidence](docs/codex-for-oss-application.md) for the current review package.

Useful starting points:

- [Product context](PRODUCT.md)
- [Architecture](docs/architecture.md)
- [API reference](docs/api.md)
- [Demo evidence snapshot](docs/demo-evidence.md)
- [Deployment notes](docs/deployment.md)
- [Data ethics](docs/data-ethics.md)
- [Source limits and terms](docs/source-limits.md)
- [Model card](docs/model-card.md)
- [Roadmap](docs/roadmap.md)
- [Threat model](docs/threat-model.md)
- [Maintainer automation plan](docs/maintainer-automation.md)
- [Codex for OSS application evidence](docs/codex-for-oss-application.md)
- [Changelog](CHANGELOG.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## Why This Exists

Most idea lists are generic. TaskSignal is a task-replacement radar: it looks for specific repeated workflows people hate doing, such as exporting Stripe data into a spreadsheet every Friday and turning it into a client report.

## Who Should Use This

TaskSignal is for maintainers, builders, indie hackers, developer-tool teams, and researchers who want a local-first way to review public pain signals before deciding what to build. It is not for scraping private communities, profiling individuals, spam, outreach automation, or replacing human product judgment.

## What It Does

- Loads demo fixture data with no API keys.
- Saves repeatable research projects with source, query, limit, labels, and last scan status.
- Reports integration readiness without exposing secret values.
- Normalizes Reddit, Hacker News, GitHub Issues, Stack Exchange, and fixture-style records.
- Stores author hashes instead of raw usernames by default.
- Detects complaints, manual workflows, tool requests, workarounds, buying intent, and confusion.
- Generates local embeddings with `sentence-transformers/all-MiniLM-L6-v2` when available.
- Falls back to deterministic local vectors when the model is unavailable.
- Clusters signals with a local thematic fallback by default, with optional DBSCAN when `TASKSIGNAL_USE_SKLEARN_CLUSTERING=1`.
- Scores opportunities using frequency, recency, pain, concreteness, buying intent, feasibility, and competition penalty.
- Generates opportunity cards, full Codex-ready build prompts, and richer Codex task packs.

## Architecture

```mermaid
flowchart TD
  A[Public sources and fixtures] --> B[Ingestion connectors]
  B --> C[Normalizer and deduplicator]
  C --> D[(PostgreSQL + pgvector)]
  D --> E[Pain and task detector]
  E --> F[Embedding service]
  F --> G[Thematic fallback clustering / optional DBSCAN]
  G --> H[Opportunity scoring]
  H --> I[Prompt generator]
  I --> J[FastAPI API]
  J --> K[Next.js dashboard]
```

## Tech Stack

Frontend: Next.js, TypeScript, Tailwind CSS, TanStack Query, Recharts, React Markdown, Zod-ready types.

Backend: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, pgvector, pytest, ruff, scikit-learn.

ML/NLP: sentence-transformers with local-only load when the model cache exists, deterministic fallback vectors, optional DBSCAN clustering, rule-based signal detector.

Infra: Docker Compose, Makefile, GitHub Actions CI, scheduled ingestion template.

## Quickstart

```bash
cp .env.example .env
make up
```

Open the frontend at [http://localhost:3000](http://localhost:3000), go to Projects, save a research workflow, then run it. For a first proof path, go to Dashboard and click **Process demo data**. To use live public data, choose a source, query, and limit in **Live source**, then click **Run scan**.

If setup fails or a fresh checkout looks incomplete, run:

```bash
make doctor
```

API health check:

```bash
curl http://localhost:8000/health
```

## Local Development

Run the API and frontend separately:

```bash
cd apps/api
uvicorn app.main:app --reload
```

```bash
cd apps/web
npm run dev
```

Run checks before publishing changes:

```bash
make test
make lint
make verify
```

Run the release-readiness gate before tagging a release:

```bash
make release-check
```

## Distribution

TaskSignal is currently an application repository, not a published Python or npm library. Use the source checkout or Docker Compose workflow above. Reusable packages may be split out later if a stable library boundary emerges.

## Reviewer Quick Check

For a quick public review, inspect:

- [Latest release](https://github.com/Yurii201811/tasksignal/releases/tag/v0.1.3)
- [Open contributor issues](https://github.com/Yurii201811/tasksignal/issues)
- [Release-readiness workflow](https://github.com/Yurii201811/tasksignal/actions/workflows/release-check.yml)
- [Demo evidence snapshot](docs/demo-evidence.md)
- [Threat model](docs/threat-model.md)

## Repository Layout

```text
apps/api      FastAPI backend, ML pipeline, database models, tests
apps/web      Next.js dashboard, opportunity views, prompt export UI
data          Demo fixtures for local-first processing
docs          Architecture, API, deployment, ethics, and model notes
notebooks     Classifier training and evaluation workbooks
```

## Fixture Demo Mode

Fixture mode is the default. It loads records from `data/fixtures`, processes them end to end, and should generate at least five opportunity cards:

- AI-generated code audit tool
- Early-stage SaaS lead/community signal radar
- Simple onboarding drop-off analyzer
- GitHub Actions workflow debugging assistant
- Spreadsheet-to-report automation helper

## API Connector Setup

Live scans use official APIs and keep the same local-first scoring/generation pipeline as fixture mode. The unauthenticated `POST /api/scans` endpoint is restricted to public API-safe sources (`fixture` and `hackernews`) so network callers cannot spend server-side credentials or retrieve data visible to server-side tokens.

Trusted operators can still configure the internal connector pipeline with source credentials when running controlled jobs outside the public endpoint:

- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`
- `GITHUB_TOKEN`
- `STACK_EXCHANGE_KEY`

Hacker News works without credentials through the public Firebase API. GitHub and Stack Exchange can run without keys at lower rate limits. Reddit requires OAuth credentials. No paid LLM key is required. `LLM_PROVIDER=none` is the default.

`PUBLIC_SCAN_SOURCES` can narrow the public endpoint further, for example to `hackernews` only. Credentialed sources such as GitHub, Reddit, and Stack Exchange stay reserved for trusted internal scan jobs.

Browser-triggered runs of credentialed sources are available through saved
research projects only when `OPERATOR_SCAN_TOKEN` is configured on the API and
the same token is entered locally in the Projects or Integrations page. This
keeps hosted deployments from silently spending server-side credentials while
still letting trusted local operators connect APIs.

Destructive fixture resets require `DEMO_RESET_TOKEN` and the matching `X-Demo-Reset-Token` request header. The normal dashboard demo-processing action is non-destructive by default.

## Codex And Agent Handoff

Each opportunity can export:

- A generated Codex prompt.
- An evidence bundle.
- A Codex task pack with objective, suggested MVP, score, evidence, acceptance
  criteria, privacy constraints, and recommended Codex flow.

Task packs are designed for users who want to use their own signed-in Codex app,
CLI, IDE extension, or Codex web session. They do not spend ChatGPT/Codex plan
usage from the TaskSignal backend. A repo-local skill package is available at
`skills/tasksignal-opportunity-builder` for agents that can load Codex-style
skills.

## ML/NLP Approach

The MVP uses transparent rules first. It scores pain phrases, repetition phrases, tool requests, buying intent, and task concreteness hints. Embeddings use `sentence-transformers/all-MiniLM-L6-v2` only when locally available; otherwise deterministic vectors keep the demo working.

## Scoring Formula

```text
opportunity_score =
  0.25 * frequency_score
+ 0.20 * recency_score
+ 0.20 * pain_intensity_score
+ 0.15 * task_concreteness_score
+ 0.10 * buying_intent_score
+ 0.10 * feasibility_score
- 0.10 * competition_penalty
```

## Privacy And Ethics

TaskSignal is designed for public-data research, product discovery, and learning. It does not store raw usernames by default, preserves source URLs for attribution, respects API boundaries, and should not be used for spam or harassment workflows.

Before enabling live connectors, review [Data ethics](docs/data-ethics.md), configure API credentials through environment variables or GitHub repository secrets, and avoid committing `.env` files or exported datasets.

## Example Generated Opportunity

**Developers need clearer GitHub Actions failure diagnosis**

Problem: teams spend repetitive time reading noisy CI logs, searching YAML errors, and guessing root causes.

Suggested MVP: a CI log summarizer and workflow linter that identifies likely YAML mistakes, dependency failures, and next fixes.

## Example Generated Codex Prompt

```markdown
# Build Developers need clearer GitHub Actions failure diagnosis

You are a senior full-stack engineer. Build a working MVP...
```

## Portfolio Notes

This repository demonstrates full-stack engineering, API design, Python backend development, TypeScript frontend development, PostgreSQL/pgvector modeling, ML/NLP pipelines, clustering, product scoring, privacy-conscious design, Docker, CI/CD, tests, and technical writing.

## Roadmap

- Publish and maintain tagged releases with changelog entries.
- Expand contributor-friendly fixtures, docs, and public issues.
- Add richer source scheduling and rate-limit state after privacy review.
- Add pgvector ANN search in production mode.
- Add reviewer workflow for human labels.

See [Roadmap](docs/roadmap.md) for maintainer tasks, security milestones, and longer-term ideas.
