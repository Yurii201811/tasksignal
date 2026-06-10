from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "check_fixture_redaction",
    ROOT / "scripts/check_fixture_redaction.py",
)
assert SPEC and SPEC.loader
check_fixture_redaction = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = check_fixture_redaction
SPEC.loader.exec_module(check_fixture_redaction)


def test_current_fixtures_pass_redaction_check() -> None:
    findings = check_fixture_redaction.check_fixture_tree(ROOT / "data" / "fixtures")

    assert findings == []


def test_unsafe_fixture_fails_redaction_check(tmp_path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    unsafe_path = fixture_dir / "github_unsafe_sample.json"
    unsafe_path.write_text(
        json.dumps(
            {
                "source": "github",
                "items": [
                    {
                        "external_id": "unsafe-1",
                        "title": "Unsafe sample",
                        "body": "Contact jane.doe@example.com about this private issue.",
                        "user": {"login": "janedoe"},
                        "api_token": "ghp_abcdefghijklmnopqrstuvwxyz123456",
                        "html_url": "https://github.com/acme/private-repo/issues/1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    findings = check_fixture_redaction.check_fixture_tree(fixture_dir)
    messages = "\n".join(finding.message for finding in findings)

    assert "author value must be an obvious synthetic placeholder" in messages
    assert "email address must not appear in fixtures" in messages
    assert "secret-like key must not appear in fixture payloads" in messages
    assert "token-like value must not appear in fixtures" in messages
    assert "URL looks private or environment-specific" in messages


def test_unsupported_source_fails_redaction_check(tmp_path) -> None:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "unknown_sample.json").write_text(
        json.dumps({"source": "discord", "items": []}),
        encoding="utf-8",
    )

    findings = check_fixture_redaction.check_fixture_tree(fixture_dir)

    assert any("unsupported source" in finding.message for finding in findings)
