from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "check_fixture_redaction", ROOT / "scripts/check_fixture_redaction.py"
)
assert SPEC and SPEC.loader
check_fixture_redaction = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_fixture_redaction)


def write_fixture(root: Path, name: str, payload: dict) -> Path:
    fixture_dir = root / "data" / "fixtures"
    fixture_dir.mkdir(parents=True)
    path = fixture_dir / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_current_fixture_tree_is_sanitized() -> None:
    assert check_fixture_redaction.check_fixture_tree(ROOT) == []


def test_checker_rejects_unsafe_fixture_sample(tmp_path) -> None:
    write_fixture(
        tmp_path,
        "unsafe_sample.json",
        {
            "source": "reddit",
            "items": [
                {
                    "external_id": "unsafe-1",
                    "title": "Unsafe contributed sample",
                    "body": "Contact alice@example.com with token ghp_1234567890abcdefghijklmnop.",
                    "author": "Alice Smith",
                    "url": "https://internal.local/private/thread",
                    "api_key": "sk-1234567890abcdefghijklmnop",
                }
            ],
        },
    )

    failures = check_fixture_redaction.check_fixture_tree(tmp_path)

    assert any("email address" in failure for failure in failures)
    assert any("secret-like value" in failure for failure in failures)
    assert any("secret-like key" in failure for failure in failures)
    assert any("private-looking URL" in failure for failure in failures)
    assert any("raw-looking author" in failure for failure in failures)


def test_checker_rejects_unsupported_fixture_source(tmp_path) -> None:
    write_fixture(
        tmp_path,
        "slack_sample.json",
        {"source": "slack", "items": [{"external_id": "slack-1", "title": "Private chat"}]},
    )

    failures = check_fixture_redaction.check_fixture_tree(tmp_path)

    assert len(failures) == 1
    assert "unsupported fixture source 'slack'" in failures[0]
