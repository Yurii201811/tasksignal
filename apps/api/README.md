# TaskSignal

TaskSignal is a local-first evidence-to-build workbench for indie builders. It
collects public problem signals, preserves longitudinal research memory, groups
evidence into reviewable opportunity threads, and produces immutable,
hash-verifiable build packets.

The Python distribution contains the FastAPI application, the `tasksignal` CLI,
packaged migrations, and fixture data. The optional `mcp` extra adds the guarded
stdio MCP server. The Next.js workbench remains available from the source
repository and versioned container images; it is not bundled into the wheel.

```bash
uv tool install "tasksignal[mcp]"
tasksignal init
tasksignal migrate
tasksignal doctor
tasksignal serve
```

No paid model is required. Deterministic packet templates are authoritative;
configured Ollama or OpenAI enhancement is optional and provenance-recorded.

See the [repository documentation](https://github.com/Yurii201811/tasksignal)
for the CLI, REST, MCP, privacy, migration, and source-authorization guides.
