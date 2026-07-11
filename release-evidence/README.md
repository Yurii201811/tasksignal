# Manual Release Evidence

Alpha and beta releases rely on automated release evidence and do not claim
manual usability completion. Release candidates and GA additionally require a
versioned directory here:

```text
release-evidence/<python-version>/
  manual-gates.json
  reports/browser.md
  reports/accessibility.md
  reports/builder-1.md       # GA only; at least three distinct records
```

Generate the product-content binding after the exact app, fixtures, migrations,
dependencies, release scripts, and packet skill have been tested:

```bash
python3 scripts/release_evidence.py product-digest
```

`manual-gates.json` uses schema `tasksignal.manual-release-evidence/v1`:

```json
{
  "schema_version": "tasksignal.manual-release-evidence/v1",
  "version": "1.0.0rc1",
  "product_digest": "sha256:<64 lowercase hex characters>",
  "browser": {
    "path": "reports/browser.md",
    "sha256": "<64 lowercase hex characters>",
    "desktop": true,
    "narrow": true
  },
  "accessibility": {
    "path": "reports/accessibility.md",
    "sha256": "<64 lowercase hex characters>",
    "keyboard": true,
    "reduced_motion": true
  },
  "builders": []
}
```

For GA, `builders` must contain at least three completed records with distinct,
opaque IDs and evidence path/hash objects. Do not store names, email addresses,
raw source identities, private data, or credentials. The publication workflow
recomputes the product digest and report hashes, then embeds the validated
summary in an immutable evidence manifest bound to the exact tag SHA and Actions
run. Missing, stale, malformed, duplicate, or tampered evidence fails closed.
