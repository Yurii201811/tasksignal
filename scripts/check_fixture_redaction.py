#!/usr/bin/env python3
"""Validate that contributed fixture files stay sanitized."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "data" / "fixtures"

ALLOWED_SOURCES = {"github", "hackernews", "reddit", "stackexchange"}

SECRET_KEY_PARTS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "client_id",
    "client_secret",
    "password",
    "private_key",
    "secret",
    "token",
}

SECRET_VALUE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
]

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s<>'\"()]+", re.IGNORECASE)
AUTHOR_FIELD_KEYS = {"author", "by", "display_name", "login", "owner", "raw_author", "user", "username"}
AUTHOR_HANDLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
SYNTHETIC_IDENTITY_MARKERS = {
    "agency",
    "backend",
    "bootstrapped",
    "builder",
    "burnout",
    "ci",
    "consultant",
    "contributor",
    "demo",
    "dev",
    "edge",
    "engineer",
    "example",
    "fake",
    "finance",
    "fixture",
    "founder",
    "frontend",
    "growth",
    "hn",
    "lead",
    "maintainer",
    "octocat",
    "ops",
    "pm",
    "qa",
    "release",
    "saas",
    "sample",
    "ship",
    "solo",
    "test",
    "tiny",
    "user",
}

PRIVATE_HOST_SUFFIXES = (".corp", ".internal", ".local", ".private")


def iter_fixture_files(root: Path = ROOT) -> list[Path]:
    fixture_dir = root / "data" / "fixtures"
    if not fixture_dir.exists():
        return []
    return sorted(fixture_dir.rglob("*.json"))


def _is_secret_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in SECRET_KEY_PARTS)


def _is_private_host(hostname: str) -> bool:
    host = hostname.lower().strip("[]")
    if host in {"localhost", "metadata.google.internal"} or host.endswith(PRIVATE_HOST_SUFFIXES):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def _looks_synthetic_author(value: str) -> bool:
    stripped = value.strip()
    lowered = stripped.lower()
    if not lowered:
        return True
    if EMAIL_PATTERN.search(lowered) or URL_PATTERN.search(lowered):
        return False
    if stripped != lowered or lowered.startswith("@") or any(char.isspace() for char in lowered):
        return False
    if not AUTHOR_HANDLE_PATTERN.fullmatch(lowered):
        return False
    handle_parts = [part for part in re.split(r"[-_\d]+", lowered) if part]
    return any(part in SYNTHETIC_IDENTITY_MARKERS for part in handle_parts)


def _iter_json_values(value: object, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, key, child
            yield from _iter_json_values(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_json_values(child, f"{path}[{index}]")


def _check_text_value(path: Path, json_path: str, value: str) -> list[str]:
    failures: list[str] = []
    if EMAIL_PATTERN.search(value):
        failures.append(f"{path}: {json_path} contains an email address")
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            failures.append(f"{path}: {json_path} contains a secret-like value")
            break
    for raw_url in URL_PATTERN.findall(value):
        parsed = urlparse(raw_url.rstrip(".,;:]"))
        if parsed.hostname and _is_private_host(parsed.hostname):
            failures.append(f"{path}: {json_path} contains a private-looking URL")
        for query_key, _query_value in parse_qsl(parsed.query, keep_blank_values=True):
            if _is_secret_key(query_key):
                failures.append(f"{path}: {json_path} contains a secret-like URL query")
                break
    return failures


def check_fixture_file(path: Path, root: Path = ROOT) -> list[str]:
    rel = path.relative_to(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{rel}: invalid JSON: {exc}"]

    failures: list[str] = []
    if not isinstance(payload, dict):
        return [f"{rel}: fixture payload must be a JSON object"]
    source = payload.get("source")
    if source not in ALLOWED_SOURCES:
        failures.append(f"{rel}: unsupported fixture source {source!r}")
    if not isinstance(payload.get("items"), list):
        failures.append(f"{rel}: fixture payload must contain an items list")

    for json_path, key, value in _iter_json_values(payload):
        if _is_secret_key(key):
            failures.append(f"{rel}: {json_path} uses secret-like key {key!r}")
        if isinstance(value, str):
            failures.extend(_check_text_value(rel, json_path, value))
            if key in AUTHOR_FIELD_KEYS and not _looks_synthetic_author(value):
                failures.append(f"{rel}: {json_path} contains a raw-looking author value")
    return failures


def check_fixture_tree(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    files = iter_fixture_files(root)
    if not files:
        return [f"{root / 'data' / 'fixtures'}: no fixture JSON files found"]
    for path in files:
        failures.extend(check_fixture_file(path, root))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()

    root = args.root.resolve()
    failures = check_fixture_tree(root)
    if failures:
        print("Fixture redaction check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Fixture redaction check passed: {len(iter_fixture_files(root))} fixture files checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
