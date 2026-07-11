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

CI installs the built wheel on Python 3.11, 3.12, 3.13, and 3.14 on Linux and
also exercises the latest supported Python on macOS. The smoke starts outside
the checkout, proves the base wheel does not contain MCP, installs the `mcp`
extra separately, checks packaged migrations and fixtures, and verifies that
generated configuration is permission `0600` without printing secrets.

## Install

With uv, install the complete local-agent surface:

```bash
uv tool install "tasksignal[mcp]"
```

For the API and CLI without MCP:

```bash
uv tool install tasksignal
```

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
