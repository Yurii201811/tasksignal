# Data Ethics

TaskSignal is for research, product discovery, and learning.

Principles:

- Use public data only.
- Prefer official APIs over scraping.
- Do not store raw usernames by default.
- Store `author_hash` or `null`.
- Preserve source URLs for attribution.
- Respect rate limits.
- Avoid spam, harassment, or manipulation workflows.
- Collect only what is needed for opportunity research.

## Live Scans

Live scans use official connector APIs where available. The scan pipeline stores
normalized `author_hash` values instead of raw usernames and keeps source URLs so
ranked opportunities remain attributable. Connector responses are minimized
before storage so raw author fields from live APIs are not retained in
`raw_items`.

Set `AUTHOR_HASH_SALT` to a machine-specific value before storing live scan
results. The readiness endpoint warns when the placeholder salt is still in use
without returning the configured value.

Review [source limits and terms](source-limits.md) before enabling a connector
in a hosted deployment. The public scan API only exposes non-credentialed
sources and can be narrowed further with `PUBLIC_SCAN_SOURCES`; credentialed
sources belong in trusted internal jobs after review.

TaskSignal does not include outreach automation. Use scan results for research,
product discovery, and evidence review, not bulk replies or targeting people.

## Deletion And Reset

For local demos:

```bash
make reset-data
```

For hosted deployments, add administrative deletion endpoints or database retention policies before collecting live data.
