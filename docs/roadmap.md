# Roadmap

TaskSignal is early-stage open source. The roadmap prioritizes maintainability, privacy, and useful public-data research over opaque automation.

## Near Term

- Publish the first tagged GitHub release and keep this changelog current.
- Keep fixture demo mode green in CI and simple enough for new contributors to run.
- Add more representative parser fixtures for GitHub Issues, Hacker News, Reddit, and Stack Exchange.
- Improve dashboard empty, loading, and connector-error states.
- Add more browser-verified screenshots and keep the demo flow aligned with the current UI.

## Maintainer Workflow

- Triage incoming issues into `bug`, `enhancement`, `documentation`, `good first issue`, and `roadmap`.
- Review dependency changes with test output and a short risk note.
- Require human review before enabling new live connectors or changing stored data fields.
- Keep public releases tied to a changelog entry, `make release-check`, and a passing CI run.

## Security And Privacy

- Maintain a lightweight threat model for live connectors, prompt export, and stored public-source data.
- Add regression tests for credential handling and author-hash behavior.
- Keep source-limit and connector-terms notes current before expanding live scanning.
- Add redaction checks before accepting sample datasets from contributors.

## Later

- Add scheduled scans with explicit rate-limit state and opt-in storage retention.
- Add pgvector ANN search in production mode.
- Add reviewer workflows for human labels and quality feedback.
- Consider publishing reusable subpackages only if a stable library boundary emerges.
