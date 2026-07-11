#!/usr/bin/env python3
"""Release-readiness checks for TaskSignal."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

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

CI_RUN_URL_PATTERN = re.compile(
    r"^https://github\.com/[^/\s]+/[^/\s]+/actions/runs/\d+/?$"
)
PEP440_PRERELEASE_PATTERN = re.compile(
    r"^(?P<base>\d+\.\d+\.\d+)(?P<phase>a|b|rc)(?P<number>\d+)$"
)
CANONICAL_RELEASE_PATTERN = re.compile(
    r"^(?P<base>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))"
    r"(?:(?P<phase>a|b|rc)(?P<number>[1-9]\d*))?$"
)

REQUIRED_FILES = [
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/good_first_issue.yml",
    ".github/workflows/release-check.yml",
    ".github/workflows/publish.yml",
    "docs/cli.md",
    "docs/packaged-installation.md",
    "release-evidence/README.md",
    "spec/spec-process-cicd-publish-release.md",
    "docs/roadmap.md",
    "docs/demo-evidence.md",
    "docs/threat-model.md",
    "docs/maintainer-automation.md",
    "docs/release-prep.md",
    "docs/codex-for-oss-application.md",
    "scripts/tasksignal_cli.py",
    "skills/tasksignal-opportunity-builder/SKILL.md",
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
        if path.suffix in BLOCKED_TRACKED_SUFFIXES or any(
            part in EXCLUDED_DIRS for part in path.parts
        ):
            failures.append(f"Tracked generated or local-only file: {name}")
    return failures


def check_clean_worktree(require_clean: bool) -> list[str]:
    status = run_git(["status", "--short"])
    if require_clean and status:
        return ["Git worktree is not clean; commit or stash changes before release."]
    return []


def normalize_version(version: str) -> str:
    return version.strip().removeprefix("v")


class ReleaseVersion(NamedTuple):
    value: str
    phase: str
    is_prerelease: bool


def parse_release_version(version: str) -> ReleaseVersion:
    """Accept only the canonical release forms supported by the v1 workflow."""

    match = CANONICAL_RELEASE_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(
            "Version must be a canonical TaskSignal release: X.Y.Z, X.Y.ZaN, "
            "X.Y.ZbN, or X.Y.ZrcN."
        )
    phase = {None: "stable", "a": "alpha", "b": "beta", "rc": "rc"}[
        match.group("phase")
    ]
    return ReleaseVersion(
        value=version,
        phase=phase,
        is_prerelease=phase != "stable",
    )


def check_release_tag(tag: str | None, version: str | None) -> list[str]:
    if tag is None:
        return []
    if version is None:
        return ["Release tag could not be checked without canonical version metadata."]
    expected = f"v{version}"
    if tag == expected:
        return []
    return [f"Release tag {tag} must exactly equal {expected}."]


def npm_version_for_python(version: str) -> str:
    """Map canonical PEP 440 prereleases to ecosystem-valid npm SemVer."""

    normalized = normalize_version(version)
    match = PEP440_PRERELEASE_PATTERN.fullmatch(normalized)
    if match is None:
        return normalized
    phase = {"a": "alpha", "b": "beta", "rc": "rc"}[match.group("phase")]
    return f"{match.group('base')}-{phase}.{match.group('number')}"


def fastapi_version(path: Path, resolved_version: str | None = None) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "FastAPI"
    ]
    if len(constructors) != 1:
        raise ValueError(
            f"Expected exactly one direct FastAPI(...) constructor in {path}; "
            f"found {len(constructors)}."
        )

    version_keywords = [
        keyword for keyword in constructors[0].keywords if keyword.arg == "version"
    ]
    if len(version_keywords) != 1:
        raise ValueError(f"FastAPI version must be a string literal in {path}.")
    value = version_keywords[0].value
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return normalize_version(value.value)
    if (
        resolved_version is not None
        and isinstance(value, ast.Name)
        and value.id == "TASKSIGNAL_VERSION"
    ):
        return normalize_version(resolved_version)
    raise ValueError(
        f"FastAPI version must be a string literal or TASKSIGNAL_VERSION in {path}."
    )


def source_fallback_version(path: Path) -> str:
    """Read the source-checkout fallback used when no distribution is installed."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "installed_tasksignal_version"
    ]
    if len(functions) != 1:
        raise ValueError(
            f"Expected exactly one installed_tasksignal_version in {path}."
        )
    literal_returns = [
        node.value.value
        for node in ast.walk(functions[0])
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if len(literal_returns) != 1:
        raise ValueError(
            f"Expected exactly one literal source fallback version in {path}."
        )
    return normalize_version(literal_returns[0])


def read_project_versions() -> dict[str, str]:
    pyproject = tomllib.loads(
        (ROOT / "apps/api/pyproject.toml").read_text(encoding="utf-8")
    )
    uv_lock = tomllib.loads((ROOT / "apps/api/uv.lock").read_text(encoding="utf-8"))
    distribution_name = str(pyproject["project"]["name"])
    api_lock_package = next(
        package
        for package in uv_lock["package"]
        if package["name"] == distribution_name
    )
    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    package_lock = json.loads(
        (ROOT / "apps/web/package-lock.json").read_text(encoding="utf-8")
    )
    api_version = normalize_version(str(pyproject["project"]["version"]))
    return {
        "api": api_version,
        "api_lock": normalize_version(str(api_lock_package["version"])),
        "fastapi": fastapi_version(ROOT / "apps/api/app/main.py", api_version),
        "source_fallback": source_fallback_version(
            ROOT / "apps/api/app/core/version.py"
        ),
        "web": normalize_version(str(package["version"])),
        "web_lock_top": normalize_version(str(package_lock["version"])),
        "web_lock_root": normalize_version(
            str(package_lock["packages"][""]["version"])
        ),
    }


def check_project_versions(
    expected_version: str | None,
) -> tuple[str | None, list[str]]:
    versions = read_project_versions()
    failures: list[str] = []
    api_names = ("api", "api_lock", "fastapi", "source_fallback")
    api_versions = {versions[name] for name in api_names}
    web_versions = {versions[name] for name in ("web", "web_lock_top", "web_lock_root")}

    if len(api_versions) != 1:
        failures.append(
            "Python project versions do not match: "
            + ", ".join(f"{name}={versions[name]}" for name in api_names)
        )
    if len(web_versions) != 1:
        failures.append(
            "Web project versions do not match: "
            + ", ".join(
                f"{name}={versions[name]}"
                for name in ("web", "web_lock_top", "web_lock_root")
            )
        )

    api_version = versions["api"]
    parse_release_version(api_version)
    expected_web_version = npm_version_for_python(api_version)
    if web_versions != {expected_web_version}:
        failures.append(
            f"Web metadata must use {expected_web_version} for Python release {api_version}: "
            + ", ".join(
                f"{name}={versions[name]}"
                for name in ("web", "web_lock_top", "web_lock_root")
            )
        )

    release_version = (
        normalize_version(expected_version) if expected_version else api_version
    )
    if expected_version and api_versions != {release_version}:
        failures.append(
            f"Requested release version {release_version} does not match Python metadata: "
            + ", ".join(f"{name}={versions[name]}" for name in api_names)
        )

    return release_version if not failures or expected_version else None, failures


def safe_check_project_versions(
    expected_version: str | None,
) -> tuple[str | None, list[str]]:
    try:
        return check_project_versions(expected_version)
    except (
        OSError,
        SyntaxError,
        ValueError,
        LookupError,
        TypeError,
        StopIteration,
    ) as exc:
        return None, [
            f"Could not read project version metadata: {type(exc).__name__}: {exc}"
        ]


def check_changelog_entry(version: str | None) -> list[str]:
    if not version:
        return []

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading_pattern = re.compile(
        rf"^##\s+v?{re.escape(normalize_version(version))}\b", re.MULTILINE
    )
    if heading_pattern.search(changelog):
        return []
    return [
        f"CHANGELOG.md is missing a release heading for {normalize_version(version)}."
    ]


def derive_ci_run_url() -> str | None:
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if repository and run_id:
        return f"{server_url}/{repository}/actions/runs/{run_id}"
    return None


def check_ci_run_url(ci_run_url: str | None, require_ci_run_url: bool) -> list[str]:
    if not ci_run_url:
        if require_ci_run_url:
            return [
                "CI run URL is required; pass --ci-run-url or run inside GitHub Actions."
            ]
        return []
    if CI_RUN_URL_PATTERN.match(ci_run_url):
        return []
    return [f"CI run URL is not a GitHub Actions run URL: {ci_run_url}"]


def check_main_ancestry(
    *,
    require_main_ancestry: bool,
    commit_sha: str | None,
    main_ref: str = "origin/main",
) -> list[str]:
    if not require_main_ancestry:
        return []
    if not commit_sha or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        return ["A full GITHUB_SHA is required to verify release ancestry."]
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_sha, main_ref],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode == 0:
        return []
    return [f"Release commit {commit_sha} is not reachable from {main_ref}."]


def write_github_outputs(path: Path, version: ReleaseVersion) -> None:
    values = {
        "version": version.value,
        "phase": version.phase,
        "is_prerelease": str(version.is_prerelease).lower(),
        "npm_version": npm_version_for_python(version.value),
    }
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument(
        "--version",
        help="Release version to verify against project metadata and CHANGELOG.md.",
    )
    parser.add_argument(
        "--ci-run-url",
        help="Exact GitHub Actions run URL to record in release-prep evidence.",
    )
    parser.add_argument(
        "--require-ci-run-url",
        action="store_true",
        help="Fail unless a GitHub Actions run URL is supplied or available from CI env vars.",
    )
    parser.add_argument(
        "--tag", help="Exact Git tag to compare with canonical metadata."
    )
    parser.add_argument(
        "--require-main-ancestry",
        action="store_true",
        help="Fail unless GITHUB_SHA is reachable from origin/main.",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        help="Append validated release phase metadata to a GitHub Actions output file.",
    )
    args = parser.parse_args()

    release_version, version_failures = safe_check_project_versions(args.version)
    ci_run_url = args.ci_run_url or derive_ci_run_url()
    failures = [
        *check_required_files(),
        *check_secret_patterns(),
        *check_tracked_generated_files(),
        *check_clean_worktree(args.require_clean),
        *version_failures,
        *check_release_tag(args.tag, release_version),
        *check_changelog_entry(release_version),
        *check_ci_run_url(ci_run_url, args.require_ci_run_url),
        *check_main_ancestry(
            require_main_ancestry=args.require_main_ancestry,
            commit_sha=os.environ.get("GITHUB_SHA"),
        ),
    ]
    if failures:
        print("Release check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    clean_note = "clean worktree, " if args.require_clean else ""
    print(
        "Release check passed: "
        f"{clean_note}docs, tracked files, secret scan, version metadata, and changelog look good."
    )
    if release_version:
        print(f"Release version: {release_version}")
        if args.github_output is not None:
            write_github_outputs(
                args.github_output, parse_release_version(release_version)
            )
    if ci_run_url:
        print(f"CI run URL: {ci_run_url}")
    else:
        print("CI run URL: not supplied; pass --ci-run-url for release-prep evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
