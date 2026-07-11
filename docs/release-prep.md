# Release Prep

Use this checklist for every TaskSignal v1 alpha, beta, release candidate, and
general-availability candidate. A version is a candidate until the matching tag
and public release actually exist. These checks require no publishing
credentials and do not publish to GitHub, PyPI, or GHCR.

The staged sequence is `1.0.0a1`, `1.0.0b1`, `1.0.0rc1`, then `1.0.0`.
Version metadata, the changelog heading, the Git tag, Python distribution, web
package, and container labels must resolve to the same candidate before any
external publication.

## Required Local Gates

Run the consolidated release gate from a clean checkout at the exact candidate
commit:

```bash
make release-check
```

It runs full API/web verification, npm and Python dependency audits, isolated
base-wheel and MCP-extra installation, a fresh fixture-backed proof bundle,
proof-manifest verification, and the clean release-content check.

The component commands remain available when diagnosing one gate:

```bash
make verify
make npm-audit
make python-audit
make package-check
make release-proof
apps/api/.venv/bin/python scripts/release_check.py --require-clean
```

`make package-check` builds into a temporary directory and tests the artifact,
not the source checkout. See [Packaged Installation](packaged-installation.md)
for the macOS/Linux support matrix and the v1 WSL-only Windows boundary.

## Required GitHub Actions Evidence

The ordinary `CI` workflow protects pull requests with:

- full API and web validation;
- npm and locked Python dependency audits;
- distribution metadata checks;
- one uploaded wheel/sdist artifact with SHA-256 hashes;
- isolated base-wheel then MCP-extra smoke tests on Python 3.11-3.14 on Linux;
- the same Python 3.11-3.14 wheel matrix on macOS.

These jobs are configured release gates. Do not report cross-platform support as
live-proven until every required matrix leg completes successfully for the
candidate SHA.

The heavier `Release readiness` workflow runs on `main`, version tags, and
manual dispatch. It repeats the release-critical checks at one SHA and uploads
`release-readiness-<sha>` containing:

- the clean release-check report and exact Actions run URL;
- npm and Python audit reports;
- a verified fixture-backed proof bundle and its `MANIFEST.json`;
- checked Python distribution artifacts;
- a locked CycloneDX 1.5 SBOM covering the base and MCP dependencies;
- `SHA256SUMS`, verified before upload, covering every evidence file.

Artifact checksums are release evidence, not GitHub artifact attestations.
Trusted PyPI publishing, GHCR publication, and platform provenance remain
separate maintainer-authorized release actions. Never add long-lived publishing
tokens to this verification workflow.

## Migration and Product Evidence

Before an RC or GA release, attach evidence for fresh and copied-v0.2 SQLite and
PostgreSQL upgrades. Keep the pre-upgrade SQLite backup and migration record.
Do not claim rollback by downgrading or deleting additive v1 tables.

Also record:

- desktop and narrow Browser flows;
- accessibility checks, including keyboard and reduced-motion behavior;
- negative connector and MCP security checks;
- two-run delta, thread matching, human/agent review separation, deterministic
  packet generation, and packet-manifest verification;
- Docker/GHCR image digests and PyPI provenance after publication is approved.

GA remains blocked until three independent indie builders complete the
fixture-to-packet flow without maintainer help and that evidence is recorded.

## Evidence Template

```text
Release candidate:
Candidate commit:
Changelog heading:
CI run:
Release readiness run:
Release readiness artifact:
Full verification:
npm audit:
Python dependency audit:
Linux Python 3.11-3.14 wheel matrix:
macOS Python 3.11-3.14 wheel matrix:
Smoke proof and manifest:
Migration rehearsal:
Browser/accessibility report:
Independent builder evidence:
PyPI/GHCR provenance (after authorized publication):
Notes:
```

Do not include secret values, local database paths, raw source identities,
private scan records, or decision notes in release evidence.
