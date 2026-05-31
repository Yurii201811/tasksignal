# Maintainer Automation Plan

This document defines how TaskSignal can use Codex/API credits for open-source maintenance without overstating product adoption or automating sensitive decisions.

## Intended Uses

- Summarize public issues and pull requests for maintainer review.
- Draft test plans and risk notes for changes that touch ingestion, scoring, exports, or credentials.
- Suggest small fixes for failing CI, lint, type checks, or documentation drift.
- Draft release notes from merged changes and update the changelog.
- Run or interpret `make release-check` before tagging a release.
- Generate contributor-friendly task breakdowns from roadmap items.
- Review sample datasets for accidental secrets, raw usernames, private records, or unsupported sources.

## Non-Goals

- No automated outreach to people found in public data.
- No autonomous merging, releasing, credential changes, or account-setting changes.
- No private dataset analysis unless a contributor intentionally provides sanitized fixtures.
- No claims about adoption, downloads, or ecosystem impact without public evidence.

## Human Review Gates

Every generated maintenance output should be reviewed by a maintainer before it changes the repository, creates public issues, or appears in a release.

High-risk areas require explicit review:

- connector authentication and rate-limit behavior
- stored data fields and privacy defaults
- prompt/export content
- dependency upgrades
- release notes and public claims

## Example Credit Use Cases

- "Review this pull request diff and produce a short maintainer checklist."
- "Given this failing CI log, suggest the smallest fix and tests to rerun."
- "Turn this roadmap item into three contributor issues with acceptance criteria."
- "Check this fixture file for raw identifiers or accidental secrets."
- "Draft release notes from commits since the last tag."
