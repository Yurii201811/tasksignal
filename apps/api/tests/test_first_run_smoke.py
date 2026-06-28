from __future__ import annotations

import hashlib
import importlib.util
import json
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


def smoke_result() -> dict[str, object]:
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
        "source_breakdown": [
            {"source": "reddit", "count": 5},
            {"source": "github", "count": 4},
        ],
        "top_opportunity_id": 46,
        "top_opportunity": "Operators need spreadsheet-to-client-report automation",
        "task_pack_evidence_urls": 4,
        "task_pack_markdown": "# TaskSignal Codex Task Pack: Operators need automation\n",
        "task_pack_required_sections": 7,
        "llm_provider": "none",
        "public_scan_sources": "fixture,hackernews",
    }


def smoke_summary() -> dict[str, object]:
    return first_run_smoke.proof_summary(
        smoke_result(),
        dashboard_source_checked=True,
        live_dashboard_checked=None,
        revision="codex/first-run-proof-report @ c2567ce12345 (local changes present)",
        generated_at=datetime(2026, 6, 17, 12, 0, tzinfo=UTC),
    )


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


def test_task_pack_contract_check_uses_repo_local_skill_contract() -> None:
    complete_pack = "\n".join(
        [
            "# TaskSignal Codex Task Pack: Useful tool",
            "## Objective",
            "Build the narrow workflow described by the evidence.",
            "## Suggested MVP",
            "A local-first prototype with one useful happy path.",
            "## Evidence Score",
            "- Opportunity score: 56/100",
            "## Evidence",
            "### Evidence 1: Example",
            "- Source: fixture",
            "## Acceptance Criteria",
            "- The workflow can be verified locally.",
            "## Privacy And Safety Constraints",
            "- Do not include raw usernames or credential values.",
            "## Recommended Codex Flow",
            "1. Inspect the cited sources before implementation.",
            "",
        ]
    )

    assert first_run_smoke.check_task_pack_contract(complete_pack) == 7


def test_task_pack_contract_check_reports_missing_title_prefix() -> None:
    untitled_pack = "\n".join(
        [
            "# Useful tool",
            "## Objective",
            "Build the narrow workflow described by the evidence.",
            "## Suggested MVP",
            "A local-first prototype with one useful happy path.",
            "## Evidence Score",
            "- Opportunity score: 56/100",
            "## Evidence",
            "### Evidence 1: Example",
            "- Source: fixture",
            "## Acceptance Criteria",
            "- The workflow can be verified locally.",
            "## Privacy And Safety Constraints",
            "- Do not include raw usernames or credential values.",
            "## Recommended Codex Flow",
            "1. Inspect the cited sources before implementation.",
            "",
        ]
    )

    try:
        first_run_smoke.check_task_pack_contract(untitled_pack)
    except first_run_smoke.SmokeError as exc:
        message = str(exc)
        assert "missing task pack title prefix" in message
        assert "# TaskSignal Codex Task Pack:" in message
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected task pack without the TaskSignal title to fail validation")


def test_task_pack_contract_check_reports_duplicate_sections() -> None:
    duplicate_pack = "\n".join(
        [
            "# TaskSignal Codex Task Pack: Useful tool",
            "## Objective",
            "Build the narrow workflow described by the evidence.",
            "## Suggested MVP",
            "A local-first prototype with one useful happy path.",
            "## Evidence Score",
            "- Opportunity score: 56/100",
            "## Evidence",
            "### Evidence 1: Example",
            "- Source: fixture",
            "## Acceptance Criteria",
            "- The workflow can be verified locally.",
            "## Acceptance Criteria",
            "- This duplicate should be rejected.",
            "## Privacy And Safety Constraints",
            "- Do not include raw usernames or credential values.",
            "## Recommended Codex Flow",
            "1. Inspect the cited sources before implementation.",
            "",
        ]
    )

    try:
        first_run_smoke.check_task_pack_contract(duplicate_pack)
    except first_run_smoke.SmokeError as exc:
        message = str(exc)
        assert "duplicate required section" in message
        assert "## Acceptance Criteria" in message
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected duplicate task-pack section to fail validation")


def test_task_pack_contract_allows_generated_prompt_appendix_headings() -> None:
    pack_with_prompt_appendix = "\n".join(
        [
            "# TaskSignal Codex Task Pack: Useful tool",
            "## Objective",
            "Build the narrow workflow described by the evidence.",
            "## Suggested MVP",
            "A local-first prototype with one useful happy path.",
            "## Evidence Score",
            "- Opportunity score: 56/100",
            "## Evidence",
            "### Evidence 1: Example",
            "- Source: fixture",
            "## Acceptance Criteria",
            "- The workflow can be verified locally.",
            "## Privacy And Safety Constraints",
            "- Do not include raw usernames or credential values.",
            "## Recommended Codex Flow",
            "1. Inspect the cited sources before implementation.",
            "## Generated Build Prompt",
            "The generated prompt can contain its own markdown contract.",
            "## Evidence",
            "- This appendix heading should not count as a duplicate task-pack section.",
            "",
        ]
    )

    assert first_run_smoke.check_task_pack_contract(pack_with_prompt_appendix) == 7


def test_task_pack_contract_check_reports_missing_sections() -> None:
    incomplete_pack = "# TaskSignal Codex Task Pack: Useful tool\n## Objective\n"

    try:
        first_run_smoke.check_task_pack_contract(incomplete_pack)
    except first_run_smoke.SmokeError as exc:
        message = str(exc)
        assert "missing required section" in message
        assert "## Suggested MVP" in message
        assert "## Recommended Codex Flow" in message
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected incomplete task pack to fail contract validation")


def test_task_pack_contract_check_reports_empty_sections() -> None:
    empty_pack = "\n".join(
        [
            "# TaskSignal Codex Task Pack: Useful tool",
            "## Objective",
            "## Suggested MVP",
            "A local-first prototype with one useful happy path.",
            "## Evidence Score",
            "- Opportunity score: 56/100",
            "## Evidence",
            "### Evidence 1: Example",
            "## Acceptance Criteria",
            "- The workflow can be verified locally.",
            "## Privacy And Safety Constraints",
            "- Do not include raw usernames or credential values.",
            "## Recommended Codex Flow",
            "1. Inspect the cited sources before implementation.",
            "",
        ]
    )

    try:
        first_run_smoke.check_task_pack_contract(empty_pack)
    except first_run_smoke.SmokeError as exc:
        message = str(exc)
        assert "empty required section" in message
        assert "## Objective" in message
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected empty task-pack section to fail validation")


def test_task_pack_contract_check_reports_misordered_sections() -> None:
    misordered_pack = "\n".join(
        [
            "# TaskSignal Codex Task Pack: Useful tool",
            "## Suggested MVP",
            "A local-first prototype with one useful happy path.",
            "## Objective",
            "Build the narrow workflow described by the evidence.",
            "## Evidence Score",
            "- Opportunity score: 56/100",
            "## Evidence",
            "### Evidence 1: Example",
            "## Acceptance Criteria",
            "- The workflow can be verified locally.",
            "## Privacy And Safety Constraints",
            "- Do not include raw usernames or credential values.",
            "## Recommended Codex Flow",
            "1. Inspect the cited sources before implementation.",
            "",
        ]
    )

    try:
        first_run_smoke.check_task_pack_contract(misordered_pack)
    except first_run_smoke.SmokeError as exc:
        message = str(exc)
        assert "misordered required section" in message
        assert "## Suggested MVP" in message
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected misordered task-pack section to fail validation")


def test_proof_report_markdown_records_fixture_result_without_local_paths() -> None:
    report = first_run_smoke.proof_report_markdown(
        smoke_result(),
        dashboard_source_checked=True,
        live_dashboard_checked=None,
        revision="codex/first-run-proof-report @ c2567ce12345 (local changes present)",
        generated_at=datetime(2026, 6, 17, 12, 0, tzinfo=UTC),
    )

    assert report.startswith("# TaskSignal First-Run Proof")
    assert "Generated: 2026-06-17T12:00:00+00:00" in report
    assert (
        "Repository revision: codex/first-run-proof-report @ c2567ce12345 "
        "(local changes present)"
    ) in report
    assert "| API health | passed | status=ok |" in report
    assert (
        "| Fixture demo processing | passed | 18 raw records, 18 normalized records, "
        "17 signals, 5 clusters, 5 opportunities |"
    ) in report
    assert "| Task-pack export | passed | 4 evidence URL(s) on the top opportunity |" in report
    assert "| Task-pack structure | passed | 7 required sections present" in report
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


def test_proof_summary_records_checks_and_runtime_boundaries() -> None:
    summary = first_run_smoke.proof_summary(
        smoke_result(),
        dashboard_source_checked=True,
        live_dashboard_checked=False,
        revision="codex/first-run-proof-report @ c2567ce12345 (local changes present)",
        generated_at=datetime(2026, 6, 17, 12, 0, tzinfo=UTC),
    )

    assert summary["generated_at"] == "2026-06-17T12:00:00+00:00"
    assert summary["repository_revision"] == (
        "codex/first-run-proof-report @ c2567ce12345 (local changes present)"
    )
    assert summary["checks"]["api_health"]["result"] == "passed"
    assert summary["checks"]["live_dashboard_request"]["result"] == "failed"
    assert summary["checks"]["task_pack_export"]["evidence"]["top_opportunity_id"] == 46
    assert summary["checks"]["task_pack_structure"]["evidence"]["required_sections"] == 7
    assert summary["source_breakdown"] == [
        {"source": "github", "count": 4},
        {"source": "reddit", "count": 5},
    ]
    assert summary["runtime_boundaries"]["llm_provider"] == "none"
    assert "local database paths" in summary["runtime_boundaries"]["omitted"]


def test_repository_revision_reports_unavailable_when_git_is_missing(monkeypatch) -> None:
    def fake_git_output(_args: list[str], *, cwd: Path) -> str | None:
        return None

    monkeypatch.setattr(first_run_smoke, "git_output", fake_git_output)

    assert first_run_smoke.repository_revision() == "unavailable"


def test_repository_revision_marks_dirty_tree(monkeypatch) -> None:
    def fake_git_output(args: list[str], *, cwd: Path) -> str | None:
        if args[:2] == ["rev-parse", "--short=12"]:
            return "c2567ce12345"
        if args == ["branch", "--show-current"]:
            return "codex/first-run-proof-report"
        if args == ["status", "--porcelain"]:
            return " M scripts/first_run_smoke.py"
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr(first_run_smoke, "git_output", fake_git_output)

    assert (
        first_run_smoke.repository_revision()
        == "codex/first-run-proof-report @ c2567ce12345 (local changes present)"
    )


def test_write_proof_report_creates_parent_directory(tmp_path) -> None:
    output_path = tmp_path / "nested" / "first-run-proof.md"

    first_run_smoke.write_proof_report(output_path, "# proof\n")

    assert output_path.read_text(encoding="utf-8") == "# proof\n"


def test_write_proof_bundle_creates_review_package(tmp_path) -> None:
    first_run_smoke.write_proof_bundle(
        tmp_path / "proof-bundle",
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )

    bundle_dir = tmp_path / "proof-bundle"
    assert {entry.name for entry in bundle_dir.iterdir()} == set(first_run_smoke.PROOF_BUNDLE_FILES)
    assert (bundle_dir / "README.md").read_text(encoding="utf-8").startswith(
        "# TaskSignal First-Run Proof Bundle"
    )
    assert (bundle_dir / "first-run-proof.md").read_text(encoding="utf-8") == "# proof\n"
    summary_json = json.loads((bundle_dir / "first-run-summary.json").read_text())
    assert summary_json["checks"]["task_pack_export"]["evidence"]["evidence_urls"] == 4
    assert (
        (bundle_dir / "top-opportunity-task-pack.md").read_text(encoding="utf-8")
        == "# TaskSignal Codex Task Pack: Operators need automation\n"
    )
    manifest = json.loads((bundle_dir / "MANIFEST.json").read_text())
    manifest_files = {entry["path"]: entry for entry in manifest["files"]}
    assert set(manifest_files) == {
        "README.md",
        "first-run-proof.md",
        "first-run-summary.json",
        "top-opportunity-task-pack.md",
    }
    proof_entry = manifest_files["first-run-proof.md"]
    assert proof_entry["bytes"] == len(b"# proof\n")
    assert proof_entry["sha256"] == hashlib.sha256(b"# proof\n").hexdigest()
    readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
    assert "validated against the repo-local Codex skill contract" in readme
    assert "MANIFEST.json" in readme
    assert "smoke.db" not in readme


def test_write_proof_bundle_rejects_unexpected_stale_file(tmp_path) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    bundle_dir.mkdir()
    stale_file = bundle_dir / "old-proof.md"
    stale_file.write_text("# old proof\n", encoding="utf-8")

    try:
        first_run_smoke.write_proof_bundle(
            bundle_dir,
            "# proof\n",
            smoke_summary(),
            smoke_result(),
        )
    except first_run_smoke.SmokeError as exc:
        message = str(exc)
        assert "unexpected file" in message
        assert "old-proof.md" in message
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected stale proof-bundle file to fail validation")

    assert stale_file.read_text(encoding="utf-8") == "# old proof\n"


def test_write_proof_bundle_rejects_unexpected_stale_directory(tmp_path) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    stale_dir = bundle_dir / "screenshots"
    stale_dir.mkdir(parents=True)

    try:
        first_run_smoke.write_proof_bundle(
            bundle_dir,
            "# proof\n",
            smoke_summary(),
            smoke_result(),
        )
    except first_run_smoke.SmokeError as exc:
        message = str(exc)
        assert "unexpected file" in message
        assert "screenshots/" in message
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected stale proof-bundle directory to fail validation")

    assert stale_dir.is_dir()


def test_write_proof_bundle_allows_rerun_with_known_generated_files(tmp_path) -> None:
    bundle_dir = tmp_path / "proof-bundle"

    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# updated proof\n",
        smoke_summary(),
        smoke_result(),
    )

    assert {entry.name for entry in bundle_dir.iterdir()} == set(first_run_smoke.PROOF_BUNDLE_FILES)
    assert (bundle_dir / "first-run-proof.md").read_text(encoding="utf-8") == "# updated proof\n"


def test_skip_web_proof_run_does_not_allocate_web_port(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "first-run-proof.md"

    def fail_if_called() -> int:
        raise AssertionError("skip-web proof run should not allocate a web port")

    def fake_run_api_checks(_database_path: Path) -> dict[str, object]:
        result = smoke_result()
        result["source_breakdown"] = [{"source": "fixture", "count": 18}]
        return result

    monkeypatch.setattr(first_run_smoke, "free_port", fail_if_called)
    monkeypatch.setattr(first_run_smoke, "run_api_checks", fake_run_api_checks)
    monkeypatch.setattr(
        first_run_smoke,
        "repository_revision",
        lambda: "codex/first-run-proof-report @ c2567ce12345 (local changes present)",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["first_run_smoke.py", "--skip-web", "--proof-out", str(output_path)],
    )

    assert first_run_smoke.main() == 0
    report = output_path.read_text(encoding="utf-8")
    assert "TaskSignal First-Run Proof" in report
    assert "| Dashboard route source | skipped | not requested |" in report


def test_skip_web_proof_bundle_writes_expected_files(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "bundle"

    def fail_if_called() -> int:
        raise AssertionError("skip-web proof bundle should not allocate a web port")

    monkeypatch.setattr(first_run_smoke, "free_port", fail_if_called)
    monkeypatch.setattr(first_run_smoke, "run_api_checks", lambda _database_path: smoke_result())
    monkeypatch.setattr(first_run_smoke, "repository_revision", lambda: "main @ c2567ce12345 (clean)")
    monkeypatch.setattr(
        sys,
        "argv",
        ["first_run_smoke.py", "--skip-web", "--proof-dir", str(output_dir)],
    )

    assert first_run_smoke.main() == 0
    assert (output_dir / "README.md").exists()
    assert (output_dir / "first-run-proof.md").exists()
    assert (output_dir / "first-run-summary.json").exists()
    assert (output_dir / "top-opportunity-task-pack.md").exists()
    assert (output_dir / "MANIFEST.json").exists()
    summary = json.loads((output_dir / "first-run-summary.json").read_text())
    assert summary["repository_revision"] == "main @ c2567ce12345 (clean)"


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
