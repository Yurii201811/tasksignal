# TaskSignal Python CLI

The `tasksignal` wheel contains the FastAPI application, the local CLI,
Alembic migrations, and fixture data. It does not contain the Next.js UI.

## Install

Python 3.11 through 3.14 is supported on macOS and Linux. On Windows, use WSL.

After a candidate is published to PyPI:

```bash
uv tool install tasksignal
```

Install the optional stdio MCP server with:

```bash
uv tool install "tasksignal[mcp]"
```

Before publication, build and exercise the exact local wheel with
`make package-check`; do not substitute a source import for the artifact test.

The base wheel does not install the MCP SDK. Local semantic embeddings remain
an independent `ml` extra and are audited separately from the supported
base-plus-MCP surface. The 2026-07-11 all-extras audit reports `torch 2.12.0` /
`CVE-2025-3000` without a fixed version, so the ML extra is not alpha-supported.
No paid model is required for the fixture flow or deterministic build packets.

## First run

```bash
tasksignal init
tasksignal migrate
tasksignal doctor
tasksignal serve
```

`init` creates private data/config directories and a permission-`0600` config
file. It prints paths and status only; generated secret values are never
printed. Environment variables override file values.

Defaults follow the operating system's application-data conventions. Override
them when a portable or isolated runtime is needed:

```bash
export TASKSIGNAL_DATA_DIR=/absolute/path/to/tasksignal-data
export TASKSIGNAL_CONFIG_FILE=/absolute/path/to/tasksignal-config.env
```

`serve` binds only to loopback and refuses to start unless the database is at
the packaged Alembic head. A stale file-backed SQLite database is copied to a
timestamped, permission-`0600` backup before an upgrade.

`doctor` treats a current local schema as ready even before `serve` starts. Its
diagnostics separately report whether the API is currently reachable.

TaskSignal never guesses lineage for a nonempty unversioned schema. Inspect it
first, compare it with the named historical revision, and stamp only after
manual confirmation:

```bash
tasksignal migrate --fingerprint --json
tasksignal migrate \
  --stamp-revision 0006_decision_workbench \
  --expected-fingerprint <sha256> \
  --acknowledge-schema-matches-revision
tasksignal migrate
```

Unknown Alembic revisions are refused rather than overwritten.

## Commands

The primary local commands are:

```text
tasksignal init
tasksignal migrate
tasksignal serve
tasksignal doctor
tasksignal mcp
```

API-backed operations use noun-first command groups:

```text
tasksignal projects ...
tasksignal runs ...
tasksignal opportunities ...
tasksignal evidence ...
tasksignal packets ...
tasksignal sessions ...
```

Use `tasksignal <group> --help` and `tasksignal <group> <command> --help` for
the exact arguments. These commands target canonical `/api/v1` routes. The API
URL precedence is `--api-url`, `TASKSIGNAL_API_URL`, the legacy
`TASKSIGNAL_API_BASE`, then `http://127.0.0.1:8000`. Plain HTTP is accepted only
for exact loopback hosts; remote endpoints require HTTPS.

Set `TASKSIGNAL_OPERATOR_TOKEN` when the API requires the local operator token.
The token is sent only to fixed TaskSignal routes and is not forwarded across
redirects.

## Machine-readable output

Place `--json` anywhere in a command to emit exactly one stable envelope:

```json
{"data":{},"error":null,"meta":{"tasksignal_version":"1.0.0a1"},"ok":true}
```

Failures return a nonzero exit status and a redacted `error` object. Diagnostic
commands may retain safe check results in `data` when `ok` is `false`.

## MCP

`tasksignal mcp` runs stdio only. Protocol messages use stdout; prompts and
logs use stderr. Reads work immediately. Writes require approval for that MCP
process in the UI or an interactive TTY, and approval expires when the process
exits or its heartbeat expires. Configured-AI packet enhancement requires a
separate approval because it may incur cost.

The MCP surface intentionally excludes deletion/reset, credentials, source-host
authorization, retention changes, arbitrary URLs, shell/filesystem operations,
and direct GitHub writes.
