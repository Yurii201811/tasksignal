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

## Deletion And Reset

For local demos:

```bash
make reset-data
```

For hosted deployments, add administrative deletion endpoints or database retention policies before collecting live data.

