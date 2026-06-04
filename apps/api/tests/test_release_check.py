from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("release_check", ROOT / "scripts/release_check.py")
assert SPEC and SPEC.loader
release_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_check)


def write_release_files(root: Path, api_version: str = "1.2.3", web_version: str = "1.2.3") -> None:
    api_dir = root / "apps" / "api"
    web_dir = root / "apps" / "web"
    api_dir.mkdir(parents=True)
    web_dir.mkdir(parents=True)
    (api_dir / "pyproject.toml").write_text(
        f'[project]\nname = "tasksignal-api"\nversion = "{api_version}"\n',
        encoding="utf-8",
    )
    (web_dir / "package.json").write_text(
        f'{{"name":"tasksignal-web","version":"{web_version}"}}\n',
        encoding="utf-8",
    )


def test_project_version_check_accepts_matching_metadata(tmp_path, monkeypatch) -> None:
    write_release_files(tmp_path)
    monkeypatch.setattr(release_check, "ROOT", tmp_path)

    version, failures = release_check.check_project_versions("1.2.3")

    assert version == "1.2.3"
    assert failures == []


def test_project_version_check_rejects_mismatched_metadata(tmp_path, monkeypatch) -> None:
    write_release_files(tmp_path, api_version="1.2.3", web_version="1.2.4")
    monkeypatch.setattr(release_check, "ROOT", tmp_path)

    version, failures = release_check.check_project_versions("1.2.3")

    assert version == "1.2.3"
    assert "Project versions do not match" in failures[0]
    assert "Requested release version 1.2.3 does not match project metadata" in failures[1]


def test_changelog_check_requires_release_heading(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(release_check, "ROOT", tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.2.3 - 2026-06-04\n\n### Added\n\n- Release prep.\n",
        encoding="utf-8",
    )

    assert release_check.check_changelog_entry("1.2.3") == []
    assert release_check.check_changelog_entry("1.2.4") == [
        "CHANGELOG.md is missing a release heading for 1.2.4."
    ]


def test_ci_run_url_can_be_derived_from_github_actions_env(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "Yurii201811/tasksignal")
    monkeypatch.setenv("GITHUB_RUN_ID", "123456789")

    assert (
        release_check.derive_ci_run_url()
        == "https://github.com/Yurii201811/tasksignal/actions/runs/123456789"
    )


def test_ci_run_url_validation_requires_actions_run_url() -> None:
    assert release_check.check_ci_run_url(None, require_ci_run_url=True) == [
        "CI run URL is required; pass --ci-run-url or run inside GitHub Actions."
    ]
    assert release_check.check_ci_run_url(
        "https://github.com/Yurii201811/tasksignal/actions/runs/123456789",
        require_ci_run_url=True,
    ) == []
    assert release_check.check_ci_run_url(
        "https://github.com/Yurii201811/tasksignal/actions",
        require_ci_run_url=True,
    ) == [
        "CI run URL is not a GitHub Actions run URL: "
        "https://github.com/Yurii201811/tasksignal/actions"
    ]
