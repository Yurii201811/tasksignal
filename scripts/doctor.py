#!/usr/bin/env python3
"""Local first-run diagnostics for TaskSignal."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "README.md",
    ".env.example",
    "docker-compose.yml",
    "Makefile",
    "apps/api/pyproject.toml",
    "apps/web/package.json",
    "apps/web/package-lock.json",
    "data/fixtures/github_issues_sample.json",
    "data/fixtures/hn_sample.json",
    "data/fixtures/reddit_sample.json",
    "data/fixtures/stackexchange_sample.json",
]

OPTIONAL_COMMANDS = ["python3", "node", "npm", "docker"]
MIN_NODE_MAJOR = 20


@dataclass
class Check:
    label: str
    status: str
    detail: str


def run(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return (completed.stdout or completed.stderr).strip().splitlines()[0]


def check_required_paths() -> list[Check]:
    checks: list[Check] = []
    for name in REQUIRED_PATHS:
        path = ROOT / name
        checks.append(
            Check(
                label=name,
                status="ok" if path.exists() else "fail",
                detail="present" if path.exists() else "missing",
            )
        )
    return checks


def check_env_file() -> Check:
    env_path = ROOT / ".env"
    if env_path.exists():
        return Check(".env", "ok", "present; values were not inspected")
    return Check(".env", "warn", "missing; run cp .env.example .env for local development")


def check_commands() -> list[Check]:
    checks: list[Check] = []
    for command in OPTIONAL_COMMANDS:
        executable = shutil.which(command)
        if executable is None:
            checks.append(Check(command, "warn", "not found on PATH"))
            continue

        version = run([command, "--version"])
        if command == "node" and version:
            major_match = re.search(r"v?(\d+)", version)
            if major_match and int(major_match.group(1)) < MIN_NODE_MAJOR:
                checks.append(
                    Check(
                        command,
                        "warn",
                        f"{version}; use Node {MIN_NODE_MAJOR}+ for the web app",
                    )
                )
                continue
        checks.append(Check(command, "ok", version or "found"))
    return checks


def check_git_generated_files() -> Check:
    tracked = run(["git", "ls-files"]) or ""
    blocked = [
        name
        for name in tracked.splitlines()
        if name.endswith((".db", ".env", ".log"))
        or any(part in {".next", ".venv", "__pycache__", "node_modules"} for part in name.split("/"))
    ]
    if blocked:
        return Check(
            "tracked generated files",
            "fail",
            f"{len(blocked)} local/generated file(s) are tracked",
        )
    return Check("tracked generated files", "ok", "none found")


def check_fixture_count() -> Check:
    fixture_dir = ROOT / "data" / "fixtures"
    count = len(list(fixture_dir.glob("*.json"))) if fixture_dir.exists() else 0
    if count >= 4:
        return Check("fixture files", "ok", f"{count} JSON fixtures found")
    return Check("fixture files", "fail", f"expected at least 4 JSON fixtures, found {count}")


def print_checks(checks: list[Check]) -> None:
    for check in checks:
        marker = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}[check.status]
        print(f"[{marker}] {check.label}: {check.detail}")


def main() -> int:
    checks = [
        *check_required_paths(),
        check_env_file(),
        *check_commands(),
        check_git_generated_files(),
        check_fixture_count(),
    ]
    print_checks(checks)

    failures = [check for check in checks if check.status == "fail"]
    warnings = [check for check in checks if check.status == "warn"]
    if failures:
        print(f"\nDoctor failed: {len(failures)} blocker(s), {len(warnings)} warning(s).")
        return 1

    print(f"\nDoctor passed: no blockers, {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
