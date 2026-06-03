# Roadmap

TaskSignal is early-stage open source. The roadmap prioritizes maintainability, privacy, and useful public-data research over opaque automation.

## Near Term

- Keep saved research projects, public scans, and fixture mode green in CI.
- Expand the Integrations page with clearer connection tests and local runtime checks.
- Keep Codex task-pack exports and the repo-local Codex skill aligned with opportunity evidence.
- Add more representative parser fixtures for GitHub Issues, Hacker News, Reddit, and Stack Exchange.
- Improve dashboard empty, loading, and connector-error states.
- Add more browser-verified screenshots and keep the demo flow aligned with the current UI.
- Add rate-limit backoff and retention-state views for scheduled source runs.

## Maintainer Workflow

- Triage incoming issues into `bug`, `enhancement`, `documentation`, `good first issue`, and `roadmap`.
- Review dependency changes with test output and a short risk note.
- Require human review before enabling new live connectors or changing stored data fields.
- Keep public releases tied to a changelog entry, `make release-check`, and a passing CI run.
- Keep the `skills/tasksignal-opportunity-builder` package aligned with the current task-pack format.

## Security And Privacy

- Maintain a lightweight threat model for live connectors, prompt export, and stored public-source data.
- Add regression tests for credential handling and author-hash behavior.
- Keep credentialed browser-triggered scans behind `OPERATOR_SCAN_TOKEN`.
- Keep source-limit and connector-terms notes current before expanding live scanning.
- Add redaction checks before accepting sample datasets from contributors.

## Later

- Add hosted-worker examples for run-due scheduling with explicit rate-limit state and opt-in storage retention.
- Add pgvector ANN search in production mode.
- Add reviewer workflows for human labels and quality feedback.
- Add an MCP server so Codex and other agents can query opportunities directly.
- Consider publishing reusable subpackages only if a stable library boundary emerges.
