from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_python_distribution_uses_public_tasksignal_name_and_lazy_mcp_extra() -> None:
    project = tomllib.loads((ROOT / "apps/api/pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["name"] == "tasksignal"
    assert project["project"]["requires-python"] == ">=3.11,<3.15"
    assert project["project"]["readme"] == "README.md"
    assert project["project"]["license"] == "MIT"
    assert project["project"]["license-files"] == ["LICENSE"]
    assert project["project"]["scripts"] == {"tasksignal": "app.cli:main"}
    assert project["tool"]["setuptools"]["package-data"] == {
        "app.resources.fixtures": ["*.json"]
    }
    assert not any(
        dependency.startswith("mcp") for dependency in project["project"]["dependencies"]
    )
    assert project["project"]["optional-dependencies"]["mcp"] == ["mcp>=1.28.1,<2"]
    assert (ROOT / "apps/api/README.md").is_file()
    assert (ROOT / "apps/api/LICENSE").read_text(encoding="utf-8").startswith("MIT License")


def test_packaged_fixtures_match_repository_first_run_fixtures() -> None:
    packaged = ROOT / "apps/api/app/resources/fixtures"
    source = ROOT / "data/fixtures"
    names = {
        "github_issues_sample.json",
        "hn_sample.json",
        "reddit_sample.json",
        "stackexchange_sample.json",
    }

    assert {path.name for path in packaged.glob("*.json")} == names
    for name in names:
        assert json.loads((packaged / name).read_text(encoding="utf-8")) == json.loads(
            (source / name).read_text(encoding="utf-8")
        )
