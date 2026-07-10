from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("release_check", ROOT / "scripts/release_check.py")
assert SPEC and SPEC.loader
release_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_check)


def write_release_files(
    root: Path,
    api_version: str = "1.2.3",
    web_version: str = "1.2.3",
    fastapi_version: str | None = None,
    api_lock_version: str | None = None,
    web_lock_top_version: str | None = None,
    web_lock_root_version: str | None = None,
) -> None:
    fastapi_version = fastapi_version or api_version
    api_lock_version = api_lock_version or api_version
    web_lock_top_version = web_lock_top_version or web_version
    web_lock_root_version = web_lock_root_version or web_version
    api_dir = root / "apps" / "api"
    web_dir = root / "apps" / "web"
    (api_dir / "app").mkdir(parents=True)
    web_dir.mkdir(parents=True)
    (api_dir / "pyproject.toml").write_text(
        f'[project]\nname = "tasksignal-api"\nversion = "{api_version}"\n',
        encoding="utf-8",
    )
    (api_dir / "uv.lock").write_text(
        'version = 1\n\n[[package]]\nname = "tasksignal-api"\n'
        f'version = "{api_lock_version}"\n',
        encoding="utf-8",
    )
    (api_dir / "app" / "main.py").write_text(
        f'app = FastAPI(version="{fastapi_version}")\n',
        encoding="utf-8",
    )
    (web_dir / "package.json").write_text(
        json.dumps({"name": "tasksignal-web", "version": web_version}) + "\n",
        encoding="utf-8",
    )
    (web_dir / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "tasksignal-web",
                "version": web_lock_top_version,
                "lockfileVersion": 3,
                "packages": {
                    "": {
                        "name": "tasksignal-web",
                        "version": web_lock_root_version,
                    }
                },
            }
        )
        + "\n",
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


def test_project_version_check_rejects_fastapi_and_lock_mismatch(
    tmp_path, monkeypatch
) -> None:
    write_release_files(
        tmp_path,
        fastapi_version="1.2.4",
        api_lock_version="1.2.5",
        web_lock_top_version="1.2.6",
        web_lock_root_version="1.2.7",
    )
    monkeypatch.setattr(release_check, "ROOT", tmp_path)

    _version, failures = release_check.check_project_versions("1.2.3")

    message = " ".join(failures)
    assert "fastapi=1.2.4" in message
    assert "api_lock=1.2.5" in message
    assert "web_lock_top=1.2.6" in message
    assert "web_lock_root=1.2.7" in message


def test_fastapi_version_ignores_unrelated_version_keywords(tmp_path) -> None:
    path = tmp_path / "main.py"
    path.write_text(
        'builder = Builder(version="9.9.9")\n'
        'app = FastAPI(version="1.2.3")\n',
        encoding="utf-8",
    )

    assert release_check.fastapi_version(path) == "1.2.3"


def test_fastapi_version_rejects_missing_constructor(tmp_path) -> None:
    path = tmp_path / "main.py"
    path.write_text('app = create_app()\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Expected exactly one direct FastAPI"):
        release_check.fastapi_version(path)


def test_fastapi_version_rejects_nonliteral_version(tmp_path) -> None:
    path = tmp_path / "main.py"
    path.write_text(
        'api_version = "1.2.3"\napp = FastAPI(version=api_version)\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="FastAPI version must be a string literal"):
        release_check.fastapi_version(path)


def test_fastapi_version_rejects_duplicate_constructors(tmp_path) -> None:
    path = tmp_path / "main.py"
    path.write_text(
        'app = FastAPI(version="1.2.3")\n'
        'other_app = FastAPI(version="1.2.3")\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Expected exactly one direct FastAPI"):
        release_check.fastapi_version(path)


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
