from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "first_run_smoke",
    ROOT / "scripts/first_run_smoke.py",
)
assert SPEC and SPEC.loader
first_run_smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = first_run_smoke
SPEC.loader.exec_module(first_run_smoke)


def test_api_env_forces_clean_sqlite_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://example")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    database_path = tmp_path / "smoke.db"

    env = first_run_smoke.api_env(database_path)

    assert env["DATABASE_URL"] == f"sqlite:///{database_path}"
    assert env["AUTO_CREATE_TABLES"] == "true"
    assert env["LLM_PROVIDER"] == "none"
    assert env["PUBLIC_SCAN_SOURCES"] == "fixture,hackernews"
    assert env["AUTHOR_HASH_SALT"] == "first-run-smoke-local-only"


def test_dashboard_source_check_requires_route_and_feature(tmp_path, monkeypatch) -> None:
    web_dir = tmp_path / "apps" / "web"
    route_dir = web_dir / "src" / "app" / "dashboard"
    feature_dir = web_dir / "src" / "features"
    route_dir.mkdir(parents=True)
    feature_dir.mkdir(parents=True)
    (route_dir / "page.tsx").write_text(
        'import { Dashboard } from "@/features/dashboard";\n',
        encoding="utf-8",
    )
    (feature_dir / "dashboard.tsx").write_text("export function Dashboard() {}\n")
    monkeypatch.setattr(first_run_smoke, "WEB_DIR", web_dir)

    first_run_smoke.run_dashboard_source_check()


def test_dashboard_source_check_rejects_unwired_route(tmp_path, monkeypatch) -> None:
    web_dir = tmp_path / "apps" / "web"
    route_dir = web_dir / "src" / "app" / "dashboard"
    feature_dir = web_dir / "src" / "features"
    route_dir.mkdir(parents=True)
    feature_dir.mkdir(parents=True)
    (route_dir / "page.tsx").write_text("export default function Page() {}\n")
    (feature_dir / "dashboard.tsx").write_text("export function Dashboard() {}\n")
    monkeypatch.setattr(first_run_smoke, "WEB_DIR", web_dir)

    try:
        first_run_smoke.run_dashboard_source_check()
    except first_run_smoke.SmokeError as exc:
        assert "not wired" in str(exc)
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected dashboard source check to reject an unwired route")
