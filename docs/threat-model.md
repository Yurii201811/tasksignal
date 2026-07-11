# Threat Model

TaskSignal is a local-first public-data research and build-planning workbench for
one operator. This document covers the source-checkout application, packaged
Python runtime, public connectors, immutable build packets, and guarded stdio
MCP. It does not treat a protected hosted preview as a multi-user service.

## Assets

- Connector and model credentials in private config files, environment
  variables, or deployment secrets.
- The operator token, demo-reset token, author-hash salt, and process-only MCP
  session secrets.
- Public-source records, source URLs, normalized evidence, author hashes, run
  history, opportunity snapshots, and thread decisions.
- Local review notes, label notes, generated artifacts, packet manifests, action
  audits, databases, backups, exports, screenshots, and logs.
- Migration lineage and package/container provenance.

## Trust Boundaries

- Browser and Next.js UI to the FastAPI API.
- CLI to an exact loopback API, or HTTPS when a remote URL is explicitly used.
- Backend to the official Reddit, Hacker News, GitHub, and Stack Exchange APIs.
- Backend to one explicitly authorized public Discourse HTTPS origin.
- Deterministic generator to optional OpenAI or local Ollama enhancement.
- MCP client to the local stdio MCP process.
- MCP process memory to hashed session/audit state in SQLite or PostgreSQL.
- API services to immutable packet artifacts and downloadable ZIP bytes.
- Source checkout or installed wheel to SQLite/PostgreSQL and Alembic resources.
- Local checkout to configured GitHub Actions and release registries.

## Supported Security Boundary

The supported default is one operator on one machine. Native packaged mode binds
only to loopback and refuses a stale schema. Docker Compose publishes PostgreSQL,
FastAPI, and Next.js on `127.0.0.1` by default.

Ordinary local decisions and human evidence labels are not backed by user
accounts. Do not expose the default API to a network or team. A hosted preview
can require one shared operator token for all `/api/` routes, but that is only a
single-operator gate. It does not provide accounts, tenancy, per-user
authorization, retention administration, or deletion workflows.

The MCP boundary is local stdio only. It is not an HTTP MCP service and has no
OAuth support. Approval authorizes one process and the complete standard
non-destructive write set; it is not a general sandbox for an untrusted agent.

## Key Risks

- **Credential exposure:** tokens or salts could leak through commits, process
  output, HTTP errors, audit summaries, packets, or screenshots.
- **Private-data drift:** contributors or operators could ingest private records,
  usernames, local notes, cookies, or sensitive screenshots into a public-data
  workflow.
- **Source abuse:** evidence could be used for profiling, spam, harassment, or
  bulk outreach rather than aggregate product research.
- **Prompt injection:** public source text or model output can contain commands,
  links, or credential-shaped data that an agent might mistake for instructions.
- **SSRF and DNS rebinding:** a configurable forum origin could resolve to a
  private address or redirect away from its approved host.
- **Oversized or hostile responses:** a public forum can return large bodies,
  malformed JSON, excessive redirects, slow responses, or misleading retry
  metadata.
- **Terms and rate-limit violations:** recurring scans can exceed an origin's
  rules or consume shared quotas.
- **Credentialed operation abuse:** an unauthenticated caller could otherwise
  spend connector or model credentials.
- **Thread lineage errors:** a false automatic match could merge distinct
  opportunities; absence in a run could be misread as deletion or resolution.
- **Packet integrity or provenance drift:** files could be changed, added, or
  generated from a stale decision after eligibility was checked.
- **Agent privilege drift:** a session approval could outlive its process, be
  replayed, or overwrite a concurrent human decision.
- **Self-evaluation:** agent-written evidence labels could inflate readiness or
  precision if treated as human confirmation.
- **Audit leakage:** append-only action records could become another store for
  secrets, raw identities, local notes, or idempotency keys.
- **Unsafe schema upgrades:** an unversioned database could be stamped or mutated
  under the wrong lineage; a failed SQLite upgrade could destroy the only copy.
- **Dependency-scope confusion:** the optional ML stack has a wider transitive
  dependency surface than the base and MCP package checks.
- **Hosted preview overreach:** a shared token can be mistaken for production
  authentication or team readiness.

## Current Mitigations

### Credentials and local runtime

- `.env`, local databases, backups, caches, exports, and build output are
  ignored by default.
- `tasksignal init` generates private data/config directories and a
  permission-`0600` secret file without printing secret values. Environment
  variables can override the file.
- Source registry writes reject secret-like configuration keys; source reads
  return redacted configuration.
- Public search, MCP reads, packet generation, and audit output use shared
  redaction and safe-URL rules.
- Packaged `serve` accepts only loopback hosts. CLI plain HTTP accepts only exact
  loopback hosts; a remote API URL must use HTTPS.

### Public-source handling

- Normalization stores salted `author_hash` values instead of raw usernames by
  default. Public search and packet/MCP surfaces omit author hashes.
- Fixture and Hacker News scans are the only default unauthenticated public scan
  paths, and `PUBLIC_SCAN_SOURCES` can narrow them further.
- Browser-triggered credentialed projects, every Discourse project, source
  mutation, and configured-model operation require the operator-token boundary.
- Connector failures and stored runtime state are sanitized before display.
- Public-source URLs are limited to safe absolute HTTP(S) values.
- Scheduling remains explicit; the web process does not hide a recurring worker.

### Discourse

- A human/operator must confirm terms for one exact HTTPS origin. The authorized
  host and port are immutable for that source until authorization is revoked.
- Origins reject credentials, paths, queries, fragments, IP literals, numeric IP
  forms, and localhost names.
- Every request resolves the hostname, rejects any non-global/private/loopback/
  link-local/multicast/reserved/unspecified address, connects to an approved IP,
  and preserves the approved host for HTTP Host and TLS SNI.
- Redirects are manual, bounded, and must remain on the same host and port.
- Environment proxies are disabled, cookies are cleared, and no forum credentials
  or private categories are supported.
- Timeout, response-byte, result, topic-detail, and redirect limits are enforced.
  `Retry-After`, last success, and sanitized failure state are retained for
  operator decisions.

### Research lineage and decisions

- Every project run snapshots its configuration and every observed item,
  including already-stored evidence.
- Deltas distinguish `new`, `seen before`, `updated`, `unchanged`, and `not
  observed this run`; absence is never described as deletion or resolution.
- Legacy runs without trustworthy linkage remain `untracked` and cannot be
  compared by inferred timestamps.
- Thread candidates stay within one project. Weighted similarity runs only
  across compatible embedding identities and requires both a confidence
  threshold and separation margin.
- Human detach records an append-only correction when an automatic match is
  wrong. Thread decisions use expected-version checks.

### Search and generation

- Semantic search returns bounded excerpts and provenance, not raw connector
  JSON, author hashes, source configuration, credentials, or local notes.
- Evidence is labeled as untrusted data in search, packet, and MCP contracts.
- Packet eligibility requires `build_candidate`, medium/strong readiness, and
  no current `sensitive_risk`.
- Packet creation rechecks the locked thread version, current snapshot, decision,
  readiness, sensitive-risk state, and source signature immediately before
  commit.
- Deterministic originals are always complete. Optional AI output is parsed,
  bounded, redacted, and stored only as `enhanced/` variants; invalid or
  unavailable output falls back without replacing originals.
- Manifests record IDs, versions, timestamps, byte counts, hashes, decision
  provenance, and source-snapshot hashes. Verification rejects missing,
  unexpected, modified, or metadata-inconsistent content before download.
- Local decision notes, raw identities, raw connector payloads, and secrets are
  excluded from packet artifacts. `github-issue.md` is a draft only.

### MCP sessions and audit

- Reads are redacted and available immediately. Writes require a live approved
  process session, the process-held raw secret, the specific capability, an
  idempotency key, and an expected version.
- The database stores only a namespaced session-secret hash. The raw secret is
  erased from runtime state on shutdown.
- A 30-second heartbeat renews a 60-second lease. Revoke, expiry, and exit are
  terminal; writes are denied afterward.
- Standard approval covers exactly six non-destructive tools. Configured-AI
  packet enhancement needs the separate `use_configured_ai` capability because
  it can consume paid or local model capacity.
- Idempotency and optimistic concurrency return structured replay/conflict
  results instead of overwriting newer state.
- Action events are append-only and store bounded redacted summaries. Public
  audit responses omit secrets, idempotency keys, raw evidence, identities, and
  local notes.
- Agent labels retain `actor_type=agent` and session provenance. Human readiness
  and precision continue to use human-confirmed labels.
- MCP exposes no deletion/reset, source-host authorization, credentials,
  retention changes, arbitrary URL fetching, shell/filesystem operations,
  direct GitHub writes, HTTP transport, or OAuth.

### Schema and release hygiene

- Packaged migrations are installed with the wheel. `serve` refuses a stale
  schema rather than creating or changing tables during startup.
- SQLite upgrades create a timestamped, private backup first. Unknown revisions
  and nonempty unversioned schemas are refused until explicit inspection,
  fingerprinting, and acknowledgement-gated stamping.
- Repository verification includes dependency, manifest, wheel, migration,
  browser, and accessibility gates. Configured workflows are not treated as
  passing evidence until their live runs complete.
- The base and `mcp` extras are the release-audited Python dependency scope. The
  optional `ml` extra must be assessed separately because it adds a materially
  larger transitive stack. This is an audit boundary, not evidence of a known
  vulnerability.

## Required Review Before Expansion

- **New connector:** document exact terms, authentication, rate limits, stored
  fields, redirects, DNS behavior, response bounds, and failure state.
- **Private source:** design consent, authorization, retention, deletion, and
  identity handling before implementation.
- **New export target:** prove that secrets, local notes, author identities, and
  private records cannot enter the default output.
- **New MCP tool or transport:** define capability, idempotency, concurrency,
  audit redaction, lifecycle, and revocation; do not weaken the stdio boundary by
  implication.
- **Automatic external write:** require a separate human approval model before
  issue creation, outreach, messaging, or release actions.
- **Hosted or team deployment:** add real authentication, tenant isolation,
  retention, deletion, administrative controls, and log redaction first.
- **ML extra release:** run a separate dependency and artifact review for the
  exact optional environment rather than inheriting the base/MCP result.
