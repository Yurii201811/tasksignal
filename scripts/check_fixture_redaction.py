#!/usr/bin/env python3
"""Check contributed fixtures for accidental private data."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_DIR = ROOT / "data" / "fixtures"

SUPPORTED_SOURCES = {"github", "hackernews", "reddit", "stackexchange"}
SECRET_KEY_PARTS = {
    "accesstoken",
    "apikey",
    "authorization",
    "clientid",
    "clientsecret",
    "cookie",
    "password",
    "privatekey",
    "secret",
    "token",
}
AUTHOR_KEYS = {"author", "by", "display_name", "login", "owner", "user", "username"}
URL_KEYS = {"html_url", "link", "permalink", "source_url", "url"}
NORMALIZED_URL_KEYS = {re.sub(r"[^a-z0-9]", "", key.lower()) for key in URL_KEYS}
PLACEHOLDER_AUTHOR_TERMS = {
    "agency",
    "backend",
    "bootstrap",
    "builder",
    "burnout",
    "ci",
    "consultant",
    "contributor",
    "demo",
    "dev",
    "edge",
    "engineer",
    "fake",
    "finance",
    "fixture",
    "founder",
    "frontend",
    "growth",
    "hn",
    "maintainer",
    "octocat",
    "ops",
    "pm",
    "qa",
    "release",
    "sample",
    "ship",
    "solo",
    "synthetic",
    "test",
    "tiny",
    "user",
}

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SECRET_VALUE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
]
PRIVATE_HOST_PATTERNS = [
    re.compile(r"(^|\.)internal$", re.IGNORECASE),
    re.compile(r"(^|\.)corp$", re.IGNORECASE),
    re.compile(r"(^|\.)local$", re.IGNORECASE),
    re.compile(r"(^|\.)private$", re.IGNORECASE),
    re.compile(r"^(localhost|127\.|10\.|192\.168\.)", re.IGNORECASE),
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", re.IGNORECASE),
]
PRIVATE_URL_PATH_PATTERN = re.compile(
    r"(^|[-_/])(private|internal|customer|prod)([-_/]|$)",
    re.IGNORECASE,
)


class Finding(NamedTuple):
    path: Path
    location: str
    message: str

    def format(self, root: Path) -> str:
        try:
            display_path = self.path.relative_to(root)
        except ValueError:
            display_path = self.path
        return f"{display_path}:{self.location}: {self.message}"


def normalized_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def is_secret_key(key: object) -> bool:
    normalized = normalized_key(key)
    return any(part in normalized for part in SECRET_KEY_PARTS)


def has_value(value: object) -> bool:
    return value not in {"", None} and value != [] and value != {}


def is_allowed_placeholder_author(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not normalized:
        return False
    tokens = {token for token in normalized.split("_") if token}
    stems = {re.sub(r"\d+$", "", token) for token in tokens}
    if (tokens | stems) & PLACEHOLDER_AUTHOR_TERMS:
        return True
    return bool(re.fullmatch(r"(contributor|user|author|fixture)[-_]?[a-z0-9]+", normalized))


def is_private_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https", "file"}:
        return False
    if parsed.scheme == "file":
        return True

    host = parsed.hostname or ""
    if any(pattern.search(host) for pattern in PRIVATE_HOST_PATTERNS):
        return True
    return bool(PRIVATE_URL_PATH_PATTERN.search(parsed.path))


def iter_json_values(value: object, location: str = "$"):
    yield location, None, value
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from iter_json_values(nested, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from iter_json_values(nested, f"{location}[{index}]")


def iter_key_values(value: object, location: str = "$"):
    if isinstance(value, dict):
        for key, nested in value.items():
            key_location = f"{location}.{key}"
            yield key_location, key, nested
            yield from iter_key_values(nested, key_location)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from iter_key_values(nested, f"{location}[{index}]")


def check_fixture_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Finding(path, "$", f"invalid JSON: {exc.msg}")]

    if not isinstance(payload, dict):
        findings.append(Finding(path, "$", "fixture file must contain a JSON object"))
        return findings

    source = str(payload.get("source", "")).strip().lower()
    if source not in SUPPORTED_SOURCES:
        supported = ", ".join(sorted(SUPPORTED_SOURCES))
        findings.append(
            Finding(path, "$.source", f"unsupported source '{source}'; use {supported}")
        )

    items = payload.get("items")
    if not isinstance(items, list):
        findings.append(Finding(path, "$.items", "fixture file must contain an items array"))

    for location, key, value in iter_key_values(payload):
        if is_secret_key(key) and has_value(value):
            findings.append(
                Finding(
                    path,
                    location,
                    "secret-like key must not appear in fixture payloads",
                )
            )

        if normalized_key(key) in AUTHOR_KEYS and isinstance(value, str):
            if not is_allowed_placeholder_author(value):
                findings.append(
                    Finding(
                        path,
                        location,
                        "author value must be an obvious synthetic placeholder",
                    )
                )

        if (
            normalized_key(key) in NORMALIZED_URL_KEYS
            and isinstance(value, str)
            and is_private_url(value)
        ):
            findings.append(
                Finding(
                    path,
                    location,
                    "URL looks private or environment-specific",
                )
            )

    for location, _key, value in iter_json_values(payload):
        if not isinstance(value, str):
            continue
        if EMAIL_PATTERN.search(value):
            findings.append(Finding(path, location, "email address must not appear in fixtures"))
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append(
                    Finding(path, location, "token-like value must not appear in fixtures")
                )
                break

    return findings


def check_fixture_tree(fixture_dir: Path = DEFAULT_FIXTURE_DIR) -> list[Finding]:
    findings: list[Finding] = []
    if not fixture_dir.exists():
        return [Finding(fixture_dir, "$", "fixture directory does not exist")]

    fixture_files = sorted(fixture_dir.rglob("*.json"))
    if not fixture_files:
        return [Finding(fixture_dir, "$", "fixture directory contains no JSON files")]

    for path in fixture_files:
        findings.extend(check_fixture_file(path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check TaskSignal fixture privacy hygiene.")
    parser.add_argument(
        "fixture_dir",
        nargs="?",
        type=Path,
        default=DEFAULT_FIXTURE_DIR,
        help="Fixture directory to scan. Defaults to data/fixtures.",
    )
    args = parser.parse_args()

    findings = check_fixture_tree(args.fixture_dir)
    if findings:
        root = args.fixture_dir.parent if args.fixture_dir.is_dir() else ROOT
        print("Fixture redaction check failed:")
        for finding in findings:
            print(f"- {finding.format(root)}")
        return 1

    print(f"Fixture redaction check passed: {args.fixture_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
