# Source Limits And Terms

TaskSignal live scans are for public-data research, product discovery, and
learning. Review this page before enabling a connector in a hosted deployment or
raising scan limits.

## Default Exposure

Local development and hosted demos default to non-credentialed sources:

```env
PUBLIC_SCAN_SOURCES=fixture,hackernews
```

`PUBLIC_SCAN_SOURCES` can narrow this further, for example to `hackernews`
only. Credentialed connectors are reserved for trusted internal scan jobs after
reviewing credential scope, stored fields, rate limits, source terms, retention,
and acceptable use. If the setting lists only credentialed sources, readiness
warns that no browser-safe public scan source is enabled and scan requests
return a 403 with `Allowed public scan sources: none`.

## Connector Notes

| Source | Credentials | MVP limit behavior | Terms and risk note |
| --- | --- | --- | --- |
| Fixture files | None | Reads local `data/fixtures` files. | Safe default for demos because it uses synthetic or curated repository data. |
| Hacker News | None | Fetches story IDs from the public Firebase API, then item JSON for the selected feed. Keep limits modest because one scan may make many item requests. | Use for research and attribution. Do not automate replies or profiling from results. |
| GitHub Issues | Optional `GITHUB_TOKEN` | Uses `per_page` up to 100. Unauthenticated requests have lower API limits; tokens may increase quota and may expose access allowed by that token. | Prefer public-only tokens with minimal scope. Do not store private issue data in public demos. |
| Stack Exchange | Optional `STACK_EXCHANGE_KEY` | Uses `pagesize` up to 100 through advanced search. Keys increase quota. | Follow Stack Exchange API terms, attribution expectations, and backoff behavior. |
| Reddit | Required OAuth app credentials | Uses OAuth search with `limit` capped at 100. | Enable only after reviewing Reddit API terms and app credentials. Do not use results for outreach, harassment, or user profiling. |

## Query Presets

Use narrow phrases that describe repeated work, failures, or workaround pain.
Completed scans with zero opportunities usually mean weak source/query fit, not
a broken connector. Check the scan record fields `signals_detected`,
`clusters_created`, `opportunities_created`, and `outcome_message` before
widening credentials or limits.

Safe examples:

| Source | Example queries |
| --- | --- |
| Hacker News | `ask`, `show`, `job`, `manual workflow` |
| GitHub Issues | `is:issue is:open "manual workflow"`, `"github actions" "error"`, `label:bug "export csv"` |
| Stack Exchange | `automation manual workflow`, `github actions log analyzer`, `export csv report` |
| Reddit | `manual workflow automation`, `spreadsheet report`, `onboarding analytics` |

## Maintainer Checklist

- Keep `LLM_PROVIDER=none` unless a maintainer intentionally reviews paid-model
  usage and prompt/data boundaries.
- Keep exported prompts focused on evidence excerpts, source URLs, and privacy
  constraints.
- Do not commit `.env`, local databases, raw API exports, or generated datasets.
- Treat connector errors and rate limits as product states, not reasons to widen
  credential scope without review.
- Re-run backend tests and the release-readiness check after changing stored
  fields, connector limits, or `PUBLIC_SCAN_SOURCES` behavior.
