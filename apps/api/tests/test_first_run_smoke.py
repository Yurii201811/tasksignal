from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "first_run_smoke",
    ROOT / "scripts/first_run_smoke.py",
)
assert SPEC and SPEC.loader
first_run_smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = first_run_smoke
SPEC.loader.exec_module(first_run_smoke)


def packet_proof_fixture() -> tuple[bytes, str]:
    originals = {
        name: f"# Fixture {name}\n".encode()
        for name in first_run_smoke.BUILD_PACKET_FILES - {"MANIFEST.json"}
    }
    manifest = {
        "schema_version": "tasksignal.build-packet/v1",
        "tasksignal_version": "1.0.0a1",
        "template_version": "deterministic-v1",
        "packet_id": "10000000-0000-0000-0000-000000000001",
        "project_id": "20000000-0000-0000-0000-000000000002",
        "run_id": "30000000-0000-0000-0000-000000000003",
        "thread_id": "40000000-0000-0000-0000-000000000004",
        "snapshot_id": "50000000-0000-0000-0000-000000000005",
        "decision_event_id": "60000000-0000-0000-0000-000000000006",
        "generated_at": "2026-07-11T12:30:45.123456Z",
        "generation_mode": "deterministic",
        "deterministic_originals_authoritative": True,
        "lineage_status": "complete",
        "source_snapshot_sha256": "a" * 64,
        "decision_sha256": "b" * 64,
        "manifest_self_hash": None,
        "manifest_self_hash_policy": (
            "MANIFEST.json is excluded to avoid recursive self-hashing; "
            "persist the manifest immutably with the packet record."
        ),
        "enhancement": {
            "requested": False,
            "status": "not_requested",
            "provider": None,
            "model": None,
        },
        "file_count": 10,
        "files": [
            {
                "path": name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in sorted(originals.items())
        ],
    }
    manifest_content = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted({**originals, "MANIFEST.json": manifest_content}.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compresslevel=9)
    return buffer.getvalue(), manifest_content.decode()


def refresh_outer_manifest(bundle_dir: Path, *artifact_names: str) -> None:
    outer_path = bundle_dir / "MANIFEST.json"
    outer = json.loads(outer_path.read_text())
    entries = {entry["path"]: entry for entry in outer["files"]}
    for name in artifact_names:
        content = (bundle_dir / name).read_bytes()
        entries[name]["bytes"] = len(content)
        entries[name]["sha256"] = hashlib.sha256(content).hexdigest()
    outer_path.write_text(json.dumps(outer, indent=2, sort_keys=True) + "\n")


def rewrite_nested_packet(
    bundle_dir: Path,
    *,
    remove_manifest_key: str | None = None,
    duplicate_manifest_entry: bool = False,
    timestamp: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0),
    compression: int = ZIP_DEFLATED,
    create_system: int = 3,
    external_attr: int = 0o100644 << 16,
    names: list[str] | None = None,
    sync_summary_sha: bool = True,
) -> None:
    archive_path = bundle_dir / "top-opportunity-build-packet.zip"
    with ZipFile(archive_path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files["MANIFEST.json"])
    if remove_manifest_key is not None:
        manifest.pop(remove_manifest_key)
    if duplicate_manifest_entry:
        manifest["files"].append(dict(manifest["files"][0]))
    manifest_content = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    files["MANIFEST.json"] = manifest_content

    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate name:.*", category=UserWarning)
        with ZipFile(buffer, "w", compression=compression) as archive:
            for name in names or sorted(files):
                info = ZipInfo(name, date_time=timestamp)
                info.compress_type = compression
                info.create_system = create_system
                info.external_attr = external_attr
                archive.writestr(info, files[name])
    archive_path.write_bytes(buffer.getvalue())
    (bundle_dir / "top-opportunity-build-packet-manifest.json").write_bytes(manifest_content)

    changed = [
        "top-opportunity-build-packet.zip",
        "top-opportunity-build-packet-manifest.json",
    ]
    if sync_summary_sha:
        summary_path = bundle_dir / "first-run-summary.json"
        summary = json.loads(summary_path.read_text())
        evidence = summary["checks"]["immutable_build_packet"]["evidence"]
        evidence["archive_bytes"] = archive_path.stat().st_size
        evidence["archive_sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        changed.append("first-run-summary.json")
    refresh_outer_manifest(bundle_dir, *changed)


def smoke_result() -> dict[str, object]:
    packet_archive, packet_manifest = packet_proof_fixture()
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
        "task_pack_required_sections": 8,
        "decision_review_state": "promising",
        "evidence_reviews": 1,
        "evaluation_reviewed_items_before": 0,
        "evaluation_reviewed_items": 1,
        "evaluation_review_coverage_before": 0.0,
        "evaluation_review_coverage": 0.2,
        "task_pack_readiness": "medium",
        "project_runs": 2,
        "identical_run_new_evidence": 0,
        "identical_run_seen_before": 18,
        "identical_run_unchanged": 18,
        "threads_after_first_run": 5,
        "threads_after_second_run": 5,
        "automatically_matched_threads": 5,
        "false_new_threads": 0,
        "human_labels": 1,
        "agent_labels": 1,
        "human_label_visible": True,
        "agent_label_visible": True,
        "agent_session_provenance": True,
        "human_precision_before_agent_label": 1.0,
        "human_precision_after_agent_label": 1.0,
        "readiness_before_agent_label": "medium",
        "readiness_after_agent_label": "medium",
        "build_candidate_state": "build_candidate",
        "build_packet_generation_mode": "deterministic",
        "build_packet_artifact_count": 10,
        "build_packet_manifested_original_count": 9,
        "build_packet_archive_byte_count": len(packet_archive),
        "build_packet_archive_sha256": hashlib.sha256(packet_archive).hexdigest(),
        "build_packet_server_verified": True,
        "build_packet_repeat_download_identical": True,
        "build_packet_immutable_fetch_identical": True,
        "build_packet_private_markers_checked": 14,
        "build_packet_private_marker_counts": {
            "local_notes": 3,
            "raw_identities": 4,
            "author_hashes": 4,
            "secret_values": 3,
        },
        "build_packet_privacy_exports": {
            "local_notes_exported": False,
            "raw_identities_exported": False,
            "author_hashes_exported": False,
            "secret_values_exported": False,
        },
        "build_packet_archive_bytes": packet_archive,
        "build_packet_manifest_content": packet_manifest,
        "build_packet_verification": {
            "valid": True,
            "errors": [],
            "missing_files": [],
            "unexpected_files": [],
            "mismatched_files": [],
        },
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
    assert env["OPERATOR_SCAN_TOKEN"] == "first-run-smoke-operator-only"
    assert env["PUBLIC_SCAN_SOURCES"] == "fixture,hackernews"
    assert env["AUTHOR_HASH_SALT"] == "first-run-smoke-local-only"


def test_fixture_raw_identity_markers_reads_pre_sanitized_selected_inputs(
    tmp_path,
) -> None:
    fixtures = {
        "reddit_sample.json": {
            "source": "reddit",
            "items": [
                {"external_id": "r-1", "author": "reddit-builder"},
                {"external_id": "r-unselected", "author": "ignore-me"},
            ],
        },
        "hn_sample.json": {
            "source": "hackernews",
            "items": [{"external_id": "hn-1", "by": "hn-builder"}],
        },
        "github_sample.json": {
            "source": "github",
            "items": [{"external_id": "gh-1", "user": {"login": "github-builder"}}],
        },
        "stackexchange_sample.json": {
            "source": "stackexchange",
            "items": [
                {
                    "external_id": "se-1",
                    "owner": {"display_name": "stack-builder"},
                }
            ],
        },
    }
    for name, payload in fixtures.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")

    markers = first_run_smoke.fixture_raw_identity_markers(
        tmp_path,
        {
            ("reddit", "r-1"),
            ("hackernews", "hn-1"),
            ("github", "gh-1"),
            ("stackexchange", "se-1"),
        },
    )

    assert markers == {
        "reddit-builder",
        "hn-builder",
        "github-builder",
        "stack-builder",
    }


def test_privacy_marker_categories_keep_runtime_secrets_separate_from_notes() -> None:
    categories = first_run_smoke.privacy_marker_categories(
        local_notes={"opportunity-note", "evidence-note", "agent-note"},
        raw_identities={"raw-author"},
        author_hashes={"author-hash"},
        runtime_secrets={"agent-process-secret", "operator-token", "author-salt"},
    )

    assert categories == {
        "local_notes": {"opportunity-note", "evidence-note", "agent-note"},
        "raw_identities": {"raw-author"},
        "author_hashes": {"author-hash"},
        "secret_values": {
            "agent-process-secret",
            "operator-token",
            "author-salt",
        },
    }


def test_api_smoke_rejects_generic_evaluation_increase_without_true_signal() -> None:
    baseline_evaluation = {
        "total_reviewable_items": 5,
        "reviewed_items": 0,
        "review_coverage": 0.0,
        "label_counts": {
            "true_signal": 0,
            "false_positive": 0,
            "unclear": 0,
            "duplicate": 0,
            "not_actionable": 0,
            "sensitive_risk": 0,
        },
        "unrecognized_latest_labels": 0,
        "precision_on_reviewed_positives": None,
        "by_source": {},
        "by_signal_type": {},
        "selection_bias_warning": "Reviewed positives are a selected subset.",
    }
    evaluation = {
        **baseline_evaluation,
        "reviewed_items": 1,
        "review_coverage": 0.2,
        "label_counts": dict(baseline_evaluation["label_counts"]),
    }

    try:
        first_run_smoke.assert_evaluation_review_progress(
            baseline_evaluation,
            evaluation,
        )
    except first_run_smoke.SmokeError as exc:
        assert "true-signal evidence review" in str(exc)
    else:  # pragma: no cover - keeps the regression failure actionable.
        raise AssertionError(
            "Expected smoke to reject an evaluation whose true_signal count did not increase"
        )


def test_identical_run_delta_requires_precise_zero_new_and_no_false_thread() -> None:
    delta = {
        "evidence_changes": {
            "new": 0,
            "seen_before": 18,
            "updated": 0,
            "unchanged": 18,
            "not_observed_this_run": 0,
        },
        "signal_changes": {
            "new": 0,
            "seen_before": 18,
            "updated": 0,
            "unchanged": 18,
            "not_observed_this_run": 0,
        },
        "opportunity_changes": {
            "new": 0,
            "updated": 0,
            "unchanged": 5,
            "not_observed_this_run": 0,
        },
    }

    first_run_smoke.assert_identical_run_delta(
        delta,
        observed_items=18,
        signal_items=18,
        opportunity_threads=5,
    )

    delta["opportunity_changes"] = {
        "new": 1,
        "updated": 0,
        "unchanged": 5,
        "not_observed_this_run": 0,
    }
    with pytest.raises(first_run_smoke.SmokeError, match="false new"):
        first_run_smoke.assert_identical_run_delta(
            delta,
            observed_items=18,
            signal_items=18,
            opportunity_threads=5,
        )


@pytest.mark.parametrize(
    ("missing_line", "expected_message"),
    [
        (
            "## Decision Context",
            "Evidence Markdown is missing Decision Context.",
        ),
        (
            "- Review state: promising",
            "Evidence Markdown is missing promising review state.",
        ),
        (
            "- Evidence readiness: medium",
            "Evidence Markdown is missing medium evidence readiness.",
        ),
    ],
)
def test_export_context_rejects_evidence_markdown_without_required_line(
    missing_line: str,
    expected_message: str,
) -> None:
    context_lines = [
        "## Decision Context",
        "- Review state: promising",
        "- Evidence readiness: medium",
    ]
    task_pack = {
        "review_state": "promising",
        "evidence_readiness": {"level": "medium"},
        "markdown": "\n".join(context_lines),
    }
    evidence_markdown = "\n".join(
        ["# Evidence Bundle", *[line for line in context_lines if line != missing_line]]
    )

    with pytest.raises(first_run_smoke.SmokeError, match=expected_message):
        first_run_smoke.assert_decision_export_context(task_pack, evidence_markdown)


def test_export_context_requires_state_and_readiness_in_both_markdown_exports() -> None:
    context = "## Decision Context\n- Review state: promising\n- Evidence readiness: medium\n"
    task_pack = {
        "review_state": "promising",
        "evidence_readiness": {"level": "medium"},
        "markdown": f"# Task Pack\n\n{context}",
    }

    readiness = first_run_smoke.assert_decision_export_context(
        task_pack,
        f"# Evidence Bundle\n\n{context}",
    )

    assert readiness == {"level": "medium"}


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
            "## Decision Context",
            "- Review state: new",
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

    assert first_run_smoke.check_task_pack_contract(complete_pack) == 8


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
            "## Decision Context",
            "- Review state: new",
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
            "## Decision Context",
            "- Review state: new",
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
            "## Decision Context",
            "- Review state: new",
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

    assert first_run_smoke.check_task_pack_contract(pack_with_prompt_appendix) == 8


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
            "## Decision Context",
            "- Review state: new",
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
            "## Decision Context",
            "- Review state: new",
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
        "Repository revision: codex/first-run-proof-report @ c2567ce12345 (local changes present)"
    ) in report
    assert "| API health | passed | status=ok |" in report
    assert (
        "| Fixture demo processing | passed | 18 raw records, 18 normalized records, "
        "17 signals, 5 clusters, 5 opportunities |"
    ) in report
    assert "| Task-pack export | passed | 4 evidence URL(s) on the top opportunity |" in report
    assert "| Task-pack structure | passed | 8 required sections present" in report
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


def test_proof_report_mentions_decision_workflow_without_local_notes() -> None:
    report = first_run_smoke.proof_report_markdown(
        smoke_result(),
        dashboard_source_checked=True,
        live_dashboard_checked=None,
        revision="codex/first-run-proof-report @ abc123 (clean)",
        generated_at=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
    )

    assert "Decision review workflow | passed" in report
    assert "state=promising" in report
    assert "1 reviewed evidence item" in report
    assert "reviewed items=0->1" in report
    assert "local notes excluded" in report
    assert "Longitudinal research memory | passed" in report
    assert "new=0, seen before=18" in report
    assert "exact matches=5, false new threads=0" in report
    assert "Actor-aware evidence review | passed" in report
    assert "agent self-grading excluded" in report
    assert "Immutable build packet | passed" in report
    assert "files=10" in report
    assert "Build-packet privacy | passed" in report


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
    assert summary["checks"]["task_pack_structure"]["evidence"]["required_sections"] == 8
    assert summary["source_breakdown"] == [
        {"source": "github", "count": 4},
        {"source": "reddit", "count": 5},
    ]
    assert summary["runtime_boundaries"]["llm_provider"] == "none"
    assert "local database paths" in summary["runtime_boundaries"]["omitted"]


def test_proof_summary_records_decision_review_workflow() -> None:
    summary = smoke_summary()

    check = summary["checks"]["decision_review_workflow"]
    assert check["result"] == "passed"
    assert check["evidence"] == {
        "review_state": "promising",
        "evidence_reviews": 1,
        "reviewed_items_before": 0,
        "reviewed_items": 1,
        "review_coverage_before": 0.0,
        "review_coverage": 0.2,
        "task_pack_readiness": "medium",
        "local_notes_exported": False,
    }


def test_proof_summary_records_v1_evidence_to_build_contract() -> None:
    summary = smoke_summary()

    memory = summary["checks"]["longitudinal_research_memory"]
    assert memory["result"] == "passed"
    assert memory["evidence"] == {
        "project_runs": 2,
        "observed_items": 18,
        "new_evidence_on_identical_run": 0,
        "unchanged_evidence_on_identical_run": 18,
        "threads_after_first_run": 5,
        "threads_after_second_run": 5,
        "automatically_matched_threads": 5,
        "false_new_threads": 0,
        "match_method": "exact_evidence",
        "match_confidence": 1.0,
    }
    actor = summary["checks"]["actor_aware_evidence_review"]["evidence"]
    assert actor["human_labels"] == 1
    assert actor["agent_labels"] == 1
    assert actor["human_precision_before_agent_label"] == 1.0
    assert actor["human_precision_after_agent_label"] == 1.0
    assert actor["agent_self_grading_excluded"] is True
    packet = summary["checks"]["immutable_build_packet"]["evidence"]
    assert packet["review_state"] == "build_candidate"
    assert packet["generation_mode"] == "deterministic"
    assert packet["artifact_count"] == 10
    assert packet["manifested_original_count"] == 9
    assert packet["server_verified"] is True
    privacy = summary["checks"]["build_packet_privacy"]["evidence"]
    assert privacy == {
        "private_markers_checked": 14,
        "marker_counts": {
            "local_notes": 3,
            "raw_identities": 4,
            "author_hashes": 4,
            "secret_values": 3,
        },
        "local_notes_exported": False,
        "raw_identities_exported": False,
        "author_hashes_exported": False,
        "secret_values_exported": False,
    }


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
    assert (
        (bundle_dir / "README.md")
        .read_text(encoding="utf-8")
        .startswith("# TaskSignal First-Run Proof Bundle")
    )
    assert (bundle_dir / "first-run-proof.md").read_text(encoding="utf-8") == "# proof\n"
    summary_json = json.loads((bundle_dir / "first-run-summary.json").read_text())
    assert summary_json["checks"]["task_pack_export"]["evidence"]["evidence_urls"] == 4
    assert (bundle_dir / "top-opportunity-task-pack.md").read_text(
        encoding="utf-8"
    ) == "# TaskSignal Codex Task Pack: Operators need automation\n"
    manifest = json.loads((bundle_dir / "MANIFEST.json").read_text())
    manifest_files = {entry["path"]: entry for entry in manifest["files"]}
    assert set(manifest_files) == {
        "README.md",
        "first-run-proof.md",
        "first-run-summary.json",
        "top-opportunity-task-pack.md",
        "top-opportunity-build-packet.zip",
        "top-opportunity-build-packet-manifest.json",
        "top-opportunity-build-packet-verification.json",
    }
    assert manifest["schema_version"] == "tasksignal.first-run-proof/v1"
    assert manifest["artifact_count"] == 7
    proof_entry = manifest_files["first-run-proof.md"]
    assert proof_entry["bytes"] == len(b"# proof\n")
    assert proof_entry["sha256"] == hashlib.sha256(b"# proof\n").hexdigest()
    readme = (bundle_dir / "README.md").read_text(encoding="utf-8")
    assert "validated against the repo-local Codex skill contract" in readme
    assert "deterministic immutable 10-file build packet" in readme
    assert "MANIFEST.json" in readme
    assert "smoke.db" not in readme
    assert (bundle_dir / "top-opportunity-build-packet.zip").read_bytes() == (
        packet_proof_fixture()[0]
    )
    packet_verification = json.loads(
        (bundle_dir / "top-opportunity-build-packet-verification.json").read_text()
    )
    assert packet_verification["valid"] is True


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


def test_verify_proof_bundle_manifest_accepts_generated_bundle(tmp_path) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )

    first_run_smoke.verify_proof_bundle_manifest(bundle_dir)


def test_verify_proof_bundle_manifest_rejects_tampered_artifact(tmp_path) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    (bundle_dir / "first-run-proof.md").write_text("# tampered proof\n", encoding="utf-8")

    try:
        first_run_smoke.verify_proof_bundle_manifest(bundle_dir)
    except first_run_smoke.SmokeError as exc:
        message = str(exc)
        assert "Proof bundle manifest verification failed" in message
        assert "byte count mismatch for first-run-proof.md" in message
        assert "sha256 mismatch for first-run-proof.md" in message
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected tampered proof bundle artifact to fail verification")


def test_verify_proof_bundle_manifest_rejects_semantically_tampered_packet_manifest(
    tmp_path,
) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    packet_manifest_path = bundle_dir / "top-opportunity-build-packet-manifest.json"
    packet_manifest_path.write_text('{"files": []}\n', encoding="utf-8")
    outer_path = bundle_dir / "MANIFEST.json"
    outer = json.loads(outer_path.read_text())
    entry = next(
        row for row in outer["files"] if row["path"] == "top-opportunity-build-packet-manifest.json"
    )
    content = packet_manifest_path.read_bytes()
    entry["bytes"] = len(content)
    entry["sha256"] = hashlib.sha256(content).hexdigest()
    outer_path.write_text(json.dumps(outer, indent=2, sort_keys=True) + "\n")

    with pytest.raises(first_run_smoke.SmokeError, match="differs from the archive"):
        first_run_smoke.verify_proof_bundle_manifest(bundle_dir)


def test_verify_proof_bundle_manifest_rejects_missing_packet_lineage_metadata(
    tmp_path,
) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    rewrite_nested_packet(bundle_dir, remove_manifest_key="decision_sha256")

    with pytest.raises(first_run_smoke.SmokeError, match="decision_sha256"):
        first_run_smoke.verify_proof_bundle_manifest(bundle_dir)


def test_verify_proof_bundle_manifest_rejects_duplicate_manifest_file_entry(
    tmp_path,
) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    rewrite_nested_packet(bundle_dir, duplicate_manifest_entry=True)

    with pytest.raises(first_run_smoke.SmokeError, match="duplicate file entries"):
        first_run_smoke.verify_proof_bundle_manifest(bundle_dir)


def test_verify_proof_bundle_manifest_cross_checks_summary_archive_sha(tmp_path) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    summary_path = bundle_dir / "first-run-summary.json"
    summary = json.loads(summary_path.read_text())
    summary["checks"]["immutable_build_packet"]["evidence"]["archive_sha256"] = "0" * 64
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    refresh_outer_manifest(bundle_dir, "first-run-summary.json")

    with pytest.raises(first_run_smoke.SmokeError, match="summary archive sha256"):
        first_run_smoke.verify_proof_bundle_manifest(bundle_dir)


def test_verify_proof_bundle_manifest_rejects_nondeterministic_packet_timestamp(
    tmp_path,
) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    rewrite_nested_packet(bundle_dir, timestamp=(2026, 7, 11, 12, 30, 44))

    with pytest.raises(first_run_smoke.SmokeError, match="deterministic timestamp"):
        first_run_smoke.verify_proof_bundle_manifest(bundle_dir)


@pytest.mark.parametrize(
    ("rewrite_kwargs", "expected"),
    [
        ({"compression": ZIP_STORED}, "DEFLATE compression"),
        ({"create_system": 0}, "Unix creator system"),
        ({"external_attr": 0o100600 << 16}, "0644 regular-file mode"),
    ],
)
def test_verify_proof_bundle_manifest_rejects_nondeterministic_packet_mode(
    tmp_path,
    rewrite_kwargs: dict[str, int],
    expected: str,
) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    rewrite_nested_packet(bundle_dir, **rewrite_kwargs)

    with pytest.raises(first_run_smoke.SmokeError, match=expected):
        first_run_smoke.verify_proof_bundle_manifest(bundle_dir)


@pytest.mark.parametrize("names_kind", ["reversed", "duplicate"])
def test_verify_proof_bundle_manifest_rejects_packet_order_or_duplicate(
    tmp_path,
    names_kind: str,
) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    names = sorted(first_run_smoke.BUILD_PACKET_FILES)
    if names_kind == "reversed":
        names.reverse()
    else:
        names.append("README.md")
    rewrite_nested_packet(bundle_dir, names=names)

    with pytest.raises(first_run_smoke.SmokeError, match="exactly 10 files"):
        first_run_smoke.verify_proof_bundle_manifest(bundle_dir)


def test_verify_proof_bundle_manifest_rejects_unmanifested_file(tmp_path) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )
    (bundle_dir / "notes.md").write_text("review notes\n", encoding="utf-8")

    try:
        first_run_smoke.verify_proof_bundle_manifest(bundle_dir)
    except first_run_smoke.SmokeError as exc:
        message = str(exc)
        assert "unexpected file" in message
        assert "notes.md" in message
    else:  # pragma: no cover - keeps the assertion message useful.
        raise AssertionError("Expected unmanifested proof bundle file to fail verification")


def test_verify_proof_dir_cli_exits_without_running_smoke(tmp_path, monkeypatch, capsys) -> None:
    bundle_dir = tmp_path / "proof-bundle"
    first_run_smoke.write_proof_bundle(
        bundle_dir,
        "# proof\n",
        smoke_summary(),
        smoke_result(),
    )

    def fail_if_called(_database_path: Path) -> dict[str, object]:
        raise AssertionError("proof bundle verification should not run smoke checks")

    monkeypatch.setattr(first_run_smoke, "run_api_checks", fail_if_called)
    monkeypatch.setattr(
        sys,
        "argv",
        ["first_run_smoke.py", "--verify-proof-dir", str(bundle_dir)],
    )

    assert first_run_smoke.main() == 0
    assert "Proof bundle manifest verified" in capsys.readouterr().out


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
    monkeypatch.setattr(
        first_run_smoke, "repository_revision", lambda: "main @ c2567ce12345 (clean)"
    )
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
