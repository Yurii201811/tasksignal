# Threat Model

TaskSignal is a local-first research app for public discussion data. This threat model covers the current MVP and live connector path.

## Assets

- API credentials in local `.env` files or GitHub repository secrets.
- Public-source records fetched from Reddit, Hacker News, GitHub Issues, and Stack Exchange.
- Normalized records, source URLs, author hashes, opportunity cards, and exported prompts.
- Local databases, generated exports, screenshots, and logs.

## Trust Boundaries

- Browser to Next.js frontend.
- Frontend to FastAPI backend.
- Backend to official public-source APIs.
- Backend to PostgreSQL/SQLite storage.
- Local checkout to GitHub Actions CI.

## Key Risks

- **Credential exposure:** connector tokens could leak through commits, logs, error messages, or exported prompts.
- **Private-data drift:** contributors may accidentally add real private datasets, raw usernames, or sensitive screenshots.
- **Source abuse:** scan results could be misused for spam, harassment, or profiling.
- **Prompt injection:** source text may include instructions that should remain evidence text, not maintainer instructions.
- **SSRF and unsafe URLs:** future connector expansion could fetch arbitrary URLs if source validation is loosened.
- **Rate-limit or terms violations:** live scans may exceed source expectations if scheduling is added without limits.
- **Credentialed scan abuse:** unauthenticated callers must not be able to run connector searches with server-side tokens.
- **Unsafe source links:** public-source URL fields must not become clickable non-http(s) links in the operator UI.
- **Weak release hygiene:** unreviewed dependencies or generated artifacts could be published unintentionally.

## Current Mitigations

- `.env`, local databases, caches, exports, and build output are ignored.
- Normalization stores `author_hash` values by default instead of raw usernames.
- Fixture mode works without external credentials or paid LLM APIs.
- Live connectors use official APIs and explicit credential configuration where required.
- Public scan exposure is limited to non-credentialed sources (`fixture` and
  `hackernews`) and can be narrowed further with `PUBLIC_SCAN_SOURCES`.
- Destructive demo resets require `DEMO_RESET_TOKEN` plus the matching
  `X-Demo-Reset-Token` header when that token is configured.
- Normalization and frontend rendering only expose absolute `http` and `https`
  source links.
- Exported prompts keep source excerpts as evidence and include privacy constraints.
- CI runs backend and frontend checks before public release work.
- Security reports are directed away from public issue details.

## Required Review Before Expansion

- New connector: document API terms, authentication, rate limits, stored fields, and failure behavior.
- New export target: confirm no secrets, raw identifiers, or private records can be included by default.
- New automation: keep human approval gates for labels, outreach, issue creation, and release actions.
- Hosted deployment: add authentication, retention policy, log redaction, and administrative deletion paths.
