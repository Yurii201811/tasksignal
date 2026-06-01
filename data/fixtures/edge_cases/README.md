# Connector edge-case fixtures

Small, sanitized fixtures that exercise connector and normalization edge cases
for each ingestion source: GitHub Issues, Hacker News, Stack Exchange, and Reddit.

These files are deliberately kept in a subdirectory. `FixtureConnector` globs
`*_sample.json` non-recursively in `data/fixtures/`, so the records here are not
loaded by the default demo and never alter the curated demo output. Tests load
them by pointing a `FixtureConnector` at this directory.

Each source file contains at least one sparse record (missing most optional
fields) and at least one malformed record (a field with an unexpected shape or
type). Usernames are obviously fake and exist only so tests can confirm raw
author fields are dropped before storage and `author_hash` is stored instead.

See `apps/api/tests/test_connector_fixtures.py` for the tests that consume these.
