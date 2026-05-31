#!/usr/bin/env python3
"""Release-readiness checks for TaskSignal."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_DIRS = {
    ".git",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
    "out",
}

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
]

REQUIRED_FILES = [
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/good_first_issue.yml",
    "docs/roadmap.md",
    "docs/threat-model.md",
    "docs/maintainer-automation.md",
    "docs/codex-for-oss-application.md",
]

BLOCKED_TRACKED_SUFFIXES = {".db", ".env", ".log"}


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def iter_repository_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return files


def check_required_files() -> list[str]:
    return [
        f"Missing required release file: {path}"
        for path in REQUIRED_FILES
        if not (ROOT / path).exists()
    ]


def check_secret_patterns() -> list[str]:
    failures: list[str] = []
    for path in iter_repository_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"Potential secret pattern in {path.relative_to(ROOT)}")
                break
    return failures


def check_tracked_generated_files() -> list[str]:
    failures: list[str] = []
    tracked = run_git(["ls-files"]).splitlines()
    for name in tracked:
        path = Path(name)
        if path.suffix in BLOCKED_TRACKED_SUFFIXES or any(part in EXCLUDED_DIRS for part in path.parts):
            failures.append(f"Tracked generated or local-only file: {name}")
    return failures


def check_clean_worktree(require_clean: bool) -> list[str]:
    status = run_git(["status", "--short"])
    if require_clean and status:
        return ["Git worktree is not clean; commit or stash changes before release."]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()

    failures = [
        *check_required_files(),
        *check_secret_patterns(),
        *check_tracked_generated_files(),
        *check_clean_worktree(args.require_clean),
    ]
    if failures:
        print("Release check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    clean_note = "clean worktree, " if args.require_clean else ""
    print(f"Release check passed: {clean_note}docs, tracked files, and secret scan look good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
