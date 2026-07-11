# Release Prep

Use this note to promote the `v0.2.0` candidate to a public TaskSignal release.
Before the matching Git tag and GitHub Release exist, describe it as a release
candidate rather than as externally published. These checks require no
publishing credentials.

## Required Evidence

1. Run the complete repository verification at the exact candidate commit:

   ```bash
   make verify
   ```

1. Confirm the web dependency audit is clean:

   ```bash
   cd apps/web
   npm audit
   ```

1. Generate a fresh credential-free proof bundle and verify its manifest:

   ```bash
   apps/api/.venv/bin/python -u scripts/first_run_smoke.py \
     --proof-dir first-run-proof-bundle
   apps/api/.venv/bin/python -u scripts/first_run_smoke.py \
     --verify-proof-dir first-run-proof-bundle
   ```

1. Confirm project metadata versions match and the release content gate passes:

   ```bash
   apps/api/.venv/bin/python scripts/release_check.py --version 0.2.0
   ```

1. Confirm `CHANGELOG.md` has a heading for the release being cut.

1. Run the release gate with a clean worktree:

   ```bash
   apps/api/.venv/bin/python scripts/release_check.py \
     --version 0.2.0 \
     --require-clean
   ```

1. Link the exact GitHub Actions run used as release evidence. In GitHub Actions,
   the script derives this from `GITHUB_REPOSITORY` and `GITHUB_RUN_ID`.
   For a local release note, pass the latest run URL explicitly:

   ```bash
   apps/api/.venv/bin/python scripts/release_check.py \
     --version 0.2.0 \
     --ci-run-url https://github.com/Yurii201811/tasksignal/actions/runs/123456789 \
     --require-ci-run-url
   ```

1. Check the `release-readiness-report` artifact from the Release readiness
   workflow and keep its run URL with the tag or release notes.

## Evidence Template

```text
Release:
Candidate commit:
Changelog heading:
Full verification:
Web npm audit:
Smoke proof bundle:
Manifest verification:
Release readiness run:
Release readiness artifact:
Worktree check:
Notes:
```

Do not include secret values, local database paths, or private scan records in
release evidence.

Tagging, publishing, and creating the GitHub Release are separate maintainer
actions performed only after the candidate commit and its evidence are reviewed.
