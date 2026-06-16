from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
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


def test_proof_report_markdown_records_fixture_result_without_local_paths() -> None:
    report = first_run_smoke.proof_report_markdown(
        {
            "health_status": "ok",
            "readiness_status": "ready",
            "raw_items_loaded": 18,
            "normalized_items_created": 18,
            "signals_detected": 17,
            "clusters_created": 5,
            "opportunities_created": 5,
            "total_items": 18,
            "stats_opportunities": 5,
            "source_breakdown": [
                {"source": "reddit", "count": 5},
                {"source": "github", "count": 4},
            ],
            "top_opportunity": "Operators need spreadsheet-to-client-report automation",
            "task_pack_evidence_urls": 4,
            "llm_provider": "none",
            "public_scan_sources": "fixture,hackernews",
        },
        dashboard_source_checked=True,
        live_dashboard_checked=None,
        generated_at=datetime(2026, 6, 17, 12, 0, tzinfo=UTC),
    )

    assert report.startswith("# TaskSignal First-Run Proof")
    assert "Generated: 2026-06-17T12:00:00+00:00" in report
    assert "| API health | passed | status=ok |" in report
    assert (
        "| Fixture demo processing | passed | 18 raw records, 18 normalized records, "
        "17 signals, 5 clusters, 5 opportunities |"
    ) in report
    assert "| Task-pack export | passed | 4 evidence URL(s) on the top opportunity |" in report
    assert "| Dashboard route source | passed | route imports the dashboard feature |" in report
    assert "| Live dashboard request | skipped | not requested |" in report
    assert "## Source Mix" in report
    assert "| github | 4 |" in report
    assert "| reddit | 5 |" in report
    assert "Operators need spreadsheet-to-client-report automation" in report
    assert "LLM_PROVIDER=none" in report
    assert "PUBLIC_SCAN_SOURCES=fixture,hackernews" in report
    assert "temporary SQLite" in report
    assert "smoke.db" not in report


def test_write_proof_report_creates_parent_directory(tmp_path) -> None:
    output_path = tmp_path / "nested" / "first-run-proof.md"

    first_run_smoke.write_proof_report(output_path, "# proof\n")

    assert output_path.read_text(encoding="utf-8") == "# proof\n"


def test_skip_web_proof_run_does_not_allocate_web_port(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "first-run-proof.md"

    def fail_if_called() -> int:
        raise AssertionError("skip-web proof run should not allocate a web port")

    def fake_run_api_checks(_database_path: Path) -> dict[str, object]:
        return {
            "health_status": "ok",
            "readiness_status": "ready",
            "raw_items_loaded": 18,
            "normalized_items_created": 18,
            "signals_detected": 17,
            "clusters_created": 5,
            "opportunities_created": 5,
            "total_items": 18,
            "stats_opportunities": 5,
            "source_breakdown": [{"source": "fixture", "count": 18}],
            "top_opportunity": "Operators need spreadsheet-to-client-report automation",
            "task_pack_evidence_urls": 4,
            "llm_provider": "none",
            "public_scan_sources": "fixture,hackernews",
        }

    monkeypatch.setattr(first_run_smoke, "free_port", fail_if_called)
    monkeypatch.setattr(first_run_smoke, "run_api_checks", fake_run_api_checks)
    monkeypatch.setattr(
        sys,
        "argv",
        ["first_run_smoke.py", "--skip-web", "--proof-out", str(output_path)],
    )

    assert first_run_smoke.main() == 0
    report = output_path.read_text(encoding="utf-8")
    assert "TaskSignal First-Run Proof" in report
    assert "| Dashboard route source | skipped | not requested |" in report


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
