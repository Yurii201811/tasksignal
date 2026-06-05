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
VENV_BIN = ROOT / ".venv" / "bin"
HOMEBREW_NODE20_BIN = Path("/opt/homebrew/opt/node@20/bin")

REQUIRED_PATHS = [
    "README.md",
    ".env.example",
    "docker-compose.yml",
    "Makefile",
    "apps/api/pyproject.toml",
    "apps/web/package.json",
    "apps/web/package-lock.json",
    "scripts/tasksignal_cli.py",
    "skills/tasksignal-opportunity-builder/SKILL.md",
    "data/fixtures/github_issues_sample.json",
    "data/fixtures/hn_sample.json",
    "data/fixtures/reddit_sample.json",
    "data/fixtures/stackexchange_sample.json",
]

MIN_NODE_MAJOR = 20


@dataclass
class Check:
    label: str
    status: str
    detail: str


def run(args: list[str | Path]) -> str | None:
    try:
        completed = subprocess.run(
            [str(arg) for arg in args],
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


def command_path(command: str) -> Path | str | None:
    if command in {"node", "npm"}:
        preferred = HOMEBREW_NODE20_BIN / command
        if preferred.exists():
            return preferred
    return shutil.which(command)


def version_major(version: str) -> int | None:
    major_match = re.search(r"v?(\d+)", version)
    return int(major_match.group(1)) if major_match else None


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


def check_runtime_commands() -> list[Check]:
    checks: list[Check] = []
    for command in ["python3", "node", "npm"]:
        executable = command_path(command)
        if executable is None:
            checks.append(Check(command, "fail", "not found; install it before running TaskSignal"))
            continue

        version = run([executable, "--version"])
        if command == "node" and version:
            major = version_major(version)
            if major is not None and major < MIN_NODE_MAJOR:
                checks.append(
                    Check(
                        command,
                        "fail",
                        f"{version}; use Node {MIN_NODE_MAJOR}+ for the Next.js web app",
                    )
                )
                continue

        source = f" via {executable}" if Path(str(executable)).is_absolute() else ""
        checks.append(Check(command, "ok", f"{version or 'found'}{source}"))

    docker = shutil.which("docker")
    if docker is None:
        checks.append(Check("docker", "warn", "not found; Docker Compose quickstart will not work"))
    else:
        checks.append(Check("docker", "ok", run([docker, "--version"]) or "found"))
    return checks


def check_python_tool(command: str, package_hint: str) -> Check:
    executable = VENV_BIN / command
    if executable.exists():
        version = run([executable, "--version"]) or "found"
        return Check(command, "ok", f"{version} via {executable.relative_to(ROOT)}")

    fallback = shutil.which(command)
    if fallback:
        version = run([fallback, "--version"]) or "found"
        return Check(command, "warn", f"{version} on PATH; prefer .venv/bin/{command}")

    return Check(
        command,
        "fail",
        f"missing; install API dev dependencies so .venv/bin/{command} exists ({package_hint})",
    )


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
        *check_runtime_commands(),
        check_python_tool("pytest", "pytest"),
        check_python_tool("ruff", "ruff"),
        check_python_tool("uvicorn", "uvicorn[standard]"),
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
