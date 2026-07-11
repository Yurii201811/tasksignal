# Packaged Installation

TaskSignal's Python distribution contains the local API, CLI, fixtures, and
Alembic migrations. The base install does not include MCP; install the `mcp`
extra only when a local agent will use `tasksignal mcp`.

## Supported Platforms

- macOS: native, Python 3.11 through 3.14.
- Linux: native, Python 3.11 through 3.14.
- Windows: WSL2 only for v1. Install and run TaskSignal inside a supported Linux
  distribution such as Ubuntu. Native PowerShell, Command Prompt, and Windows
  filesystem semantics are not release targets and are not covered by CI.

CI is configured to install the built wheel on Python 3.11, 3.12, 3.13, and
3.14 on both Linux and macOS. The smoke is designed to start outside the
checkout, prove the base wheel does not contain MCP, install the `mcp` extra
separately, check packaged migrations and fixtures, and verify that generated
configuration is permission `0600` without printing secrets. Live
cross-platform evidence remains pending until those Actions jobs complete
successfully; workflow configuration alone is not passing evidence.

## Install

This documentation does not claim that TaskSignal is already published to PyPI.
From a source checkout, install the complete local-agent surface with:

```bash
uv tool install './apps/api[mcp]'
```

For the API and CLI without MCP:

```bash
uv tool install './apps/api'
```

After a registry release exists, the equivalent package requirements are
`tasksignal[mcp]` and `tasksignal`. Verify the published version and provenance
before using those names in an installation command.

Before a package is published, maintainers can test the exact local wheel with:

```bash
make package-check
```

That target builds into a temporary directory, checks both distribution
artifacts, installs the wheel into an isolated environment, and removes the
temporary artifacts after verification.

## Initialize and Upgrade

```bash
tasksignal init
tasksignal migrate
tasksignal doctor
tasksignal serve
```

`init` creates platform-specific local data and configuration paths. The secret
configuration file is permission `0600`, and secret values are never printed.
Environment variables override generated configuration. `migrate` backs up a
SQLite database before an upgrade and refuses to guess the lineage of an
unknown or unversioned schema. `serve` refuses stale schemas and binds only to a
loopback address.

Inspect any nonempty unversioned database before using the CLI's explicit
fingerprint-and-stamp flow. Keep the generated backup until the migrated build
packet flow has been verified.

## MCP Boundary

Start the stdio MCP server only from the extra-enabled installation:

```bash
tasksignal mcp
```

MCP writes remain process-bound and require explicit local approval. The Python
wheel does not include the Next.js interface; use a source checkout or a
versioned container image for the full workbench UI.

The base and `mcp` dependency surfaces are the release-audited package scope.
The optional `ml` extra adds a materially wider transitive dependency set and
must be assessed separately. On 2026-07-11, the locked all-extras audit reports
`torch 2.12.0` as affected by `CVE-2025-3000` with no fixed version reported by
the audit. The base and MCP installs do not include torch and audit clean. Do
not treat the `ml` extra as release-supported until that finding has a reviewed
resolution or explicit risk acceptance; deterministic embeddings remain the
safe default.
