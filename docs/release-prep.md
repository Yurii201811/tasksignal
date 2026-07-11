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

The tag-only `Publish release` workflow repeats the release gates and preserves
`release-evidence-<sha>` before any registry write. That artifact binds the exact
tag SHA and Actions run to the proof manifest, audit logs, fresh/copied-v0.2
SQLite record, four-case PostgreSQL record, phase-specific manual evidence, and
the SHA-256 of every included file. Publication jobs consume that artifact; they
do not merely assume the independent `Release readiness` workflow passed.

The `pypi` and `release` environments must have required-reviewer rules before a
tag is pushed. PyPI uses Trusted Publishing through GitHub OIDC; GHCR uses the
scoped workflow token. Both container images are built first at unique full-SHA
staging references. The workflow then publishes or exact-hash-skips PyPI,
promotes the already-built digests to immutable version and full-SHA image tags,
and finally uploads a complete draft GitHub release. The draft becomes public
only after its remote filename and checksum inventory verifies. A retry refuses
to move a version/full-SHA image tag or overwrite a mismatched PyPI artifact.
A matching partial draft is completed by uploading only missing assets; any
unknown or mismatched draft asset fails closed. Any stable version receives
`latest`; alpha, beta, and RC tags never do.

All workflow actions are pinned to reviewed commit SHAs. Repository build code
runs without OIDC; attestation and PyPI jobs only download previously built
artifacts. The release SBOM names TaskSignal and its version as the CycloneDX
root component, and the release evidence manifest is attested with the Python
assets.

## Migration and Product Evidence

Every publication run records fresh and copied-v0.2 SQLite and PostgreSQL
upgrades. Keep the pre-upgrade SQLite backup and migration record. Do not claim
rollback by downgrading or deleting additive v1 tables.

The local 2026-07-11 PostgreSQL 16 + pgvector rehearsal passed fresh, copied
`0006_decision_workbench`, nonempty-unversioned refusal, and foreign-revision
refusal cases with cleanup verified. The dedicated Actions workflow is
configured, but its candidate-SHA run is still required as durable evidence.

For RC and GA, add `release-evidence/<version>/manual-gates.json` and its hashed
reports as documented in [`release-evidence/README.md`](../release-evidence/README.md).
The workflow recomputes the release-product digest, so changing API/UI code,
fixtures, migrations, dependencies, release scripts, or the packet skill makes
old manual evidence stale. Record:

- desktop and narrow Browser flows;
- accessibility checks, including keyboard and reduced-motion behavior;
- negative connector and MCP security checks;
- two-run delta, thread matching, human/agent review separation, deterministic
  packet generation, and packet-manifest verification;
- Docker/GHCR image digests and PyPI provenance after publication is approved.

GA remains machine-blocked until three independent indie builders complete the
fixture-to-packet flow without maintainer help and three distinct, completed,
hash-verified evidence records are present.

Repository settings remain external gates. Before publication, verify protected
release tags, required reviewers with self-review/admin bypass disabled where
available, deployment tag restrictions, the exact `pypi` Trusted Publisher
workflow/environment, and immutable GitHub Releases. Workflow YAML cannot prove
those settings are enabled.

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
