# Security Policy

TaskSignal is an MVP intended for local-first research and responsible public-data analysis. Please handle security reports privately and avoid posting exploit details in public issues.

## Supported Versions

The `main` branch is the supported development line.

## Reporting A Vulnerability

If you find a vulnerability, open a private GitHub security advisory for this repository or contact the repository owner directly through GitHub. Include:

- a concise description of the issue
- affected component or endpoint
- reproduction steps
- impact and suggested mitigation, if known

Please do not include real API keys, private datasets, or third-party personal data in a report.

## Secret Handling

- Keep secrets in `.env` locally or GitHub repository secrets in CI.
- Do not commit `.env`, local databases, generated exports, API credentials, model caches, or service tokens.
- Rotate credentials immediately if they are accidentally exposed.

## Data Handling

TaskSignal is designed for public data and stores author hashes by default. Live connectors should use official APIs, respect rate limits, and avoid workflows that enable spam, harassment, or manipulation.

## Live Connector Risks

Before enabling or expanding live connectors, review the stored fields, credential requirements, rate limits, and source terms. Connector errors should not print tokens, raw credentials, or private source records. Exported prompts should keep source text as evidence, not as instructions to override maintainer judgment.

## Threat Model

See [docs/threat-model.md](docs/threat-model.md) for the current lightweight threat model covering credentials, live APIs, normalized records, prompt export, and release hygiene.
