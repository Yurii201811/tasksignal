# Release Prep

Use this note before tagging a public TaskSignal release. It keeps the release
evidence concrete without requiring publishing credentials.

## Required Evidence

1. Confirm project metadata versions match:

   ```bash
   python3 scripts/release_check.py --version 0.1.3
   ```

1. Confirm `CHANGELOG.md` has a heading for the release being cut.

1. Run the release gate with a clean worktree:

   ```bash
   python3 scripts/release_check.py --version 0.1.3 --require-clean
   ```

1. Link the exact GitHub Actions run used as release evidence. In GitHub Actions,
   the script derives this from `GITHUB_REPOSITORY` and `GITHUB_RUN_ID`.
   For a local release note, pass the latest run URL explicitly:

   ```bash
   python3 scripts/release_check.py \
     --version 0.1.3 \
     --ci-run-url https://github.com/Yurii201811/tasksignal/actions/runs/123456789 \
     --require-ci-run-url
   ```

1. Check the `release-readiness-report` artifact from the Release readiness
   workflow and keep its run URL with the tag or release notes.

## Evidence Template

```text
Release:
Changelog heading:
Release readiness run:
Release readiness artifact:
Worktree check:
Notes:
```

Do not include secret values, local database paths, or private scan records in
release evidence.
