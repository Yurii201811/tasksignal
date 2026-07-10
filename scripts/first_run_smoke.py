#!/usr/bin/env python3
"""Credential-free first-run smoke check for TaskSignal."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
WEB_DIR = ROOT / "apps" / "web"
HOMEBREW_NODE20_BIN = Path("/opt/homebrew/opt/node@20/bin")
TASK_PACK_CHECKER_PATH = (
    ROOT
    / "skills"
    / "tasksignal-opportunity-builder"
    / "scripts"
    / "check_task_pack.py"
)
PROOF_BUNDLE_ARTIFACTS = [
    "README.md",
    "first-run-proof.md",
    "first-run-summary.json",
    "top-opportunity-task-pack.md",
]
PROOF_BUNDLE_MANIFEST = "MANIFEST.json"
PROOF_BUNDLE_FILES = [*PROOF_BUNDLE_ARTIFACTS, PROOF_BUNDLE_MANIFEST]


class SmokeError(RuntimeError):
    """Raised when a first-run smoke check fails."""


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen
    log_path: Path
    log_handle: object

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.log_handle.close()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def web_env(api_base: str) -> dict[str, str]:
    env = os.environ.copy()
    if HOMEBREW_NODE20_BIN.exists():
        env["PATH"] = f"{HOMEBREW_NODE20_BIN}{os.pathsep}{env.get('PATH', '')}"
    env["NEXT_PUBLIC_API_BASE_URL"] = api_base
    return env


def api_env(database_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "AUTO_CREATE_TABLES": "true",
            "AUTHOR_HASH_SALT": "first-run-smoke-local-only",
            "DATABASE_URL": f"sqlite:///{database_path}",
            "LLM_PROVIDER": "none",
            "PUBLIC_SCAN_SOURCES": "fixture,hackernews",
        }
    )
    return env


def start_process(
    name: str,
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_dir: Path,
) -> ManagedProcess:
    log_path = log_dir / f"{name}.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return ManagedProcess(
        name=name, process=process, log_path=log_path, log_handle=log_handle
    )


def request_text(url: str, *, timeout: float = 30) -> str:
    try:
        with urlopen(url, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                raise SmokeError(f"GET {url} failed with HTTP {status}")
            return response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise SmokeError(f"GET {url} could not connect: {exc.reason}") from exc


def wait_for(name: str, check, *, timeout: float, delay: float = 0.5) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            check()
            return
        except Exception as exc:  # noqa: BLE001 - report the last startup failure.
            last_error = exc
            time.sleep(delay)
    detail = f": {last_error}" if last_error else ""
    raise SmokeError(f"{name} did not become ready within {timeout:.0f}s{detail}")


def tail_log(path: Path, *, lines: int = 20) -> str:
    if not path.exists():
        return "log file is missing"
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    )


def assert_condition(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def assert_evaluation_review_progress(
    baseline_evaluation: object,
    evaluation: object,
) -> None:
    assert_condition(
        isinstance(baseline_evaluation, dict)
        and isinstance(evaluation, dict)
        and evaluation.get("reviewed_items", 0)
        > baseline_evaluation.get("reviewed_items", 0)
        and evaluation.get("review_coverage", 0.0)
        > baseline_evaluation.get("review_coverage", 0.0),
        "Evaluation did not increase after the evidence review.",
    )
    baseline_label_counts = baseline_evaluation.get("label_counts")
    evaluation_label_counts = evaluation.get("label_counts")
    assert_condition(
        isinstance(baseline_label_counts, dict)
        and isinstance(evaluation_label_counts, dict)
        and isinstance(baseline_label_counts.get("true_signal"), int)
        and isinstance(evaluation_label_counts.get("true_signal"), int)
        and evaluation_label_counts["true_signal"]
        > baseline_label_counts["true_signal"],
        "Evaluation did not record the true-signal evidence review.",
    )


def assert_decision_export_context(
    task_pack: dict[str, object],
    evidence_markdown: str,
) -> dict[str, object]:
    review_state = task_pack.get("review_state")
    assert_condition(
        review_state == "promising",
        "Task pack is missing the promising decision state.",
    )
    readiness = task_pack.get("evidence_readiness")
    assert_condition(
        isinstance(readiness, dict)
        and readiness.get("level") in {"weak", "medium", "strong"},
        "Task pack is missing evidence readiness.",
    )
    assert isinstance(readiness, dict)  # Narrowed by the smoke assertion above.
    readiness_level = readiness["level"]
    expected_lines = (
        ("## Decision Context", "Decision Context"),
        ("- Review state: promising", "promising review state"),
        (
            f"- Evidence readiness: {readiness_level}",
            f"{readiness_level} evidence readiness",
        ),
    )
    exports = (
        ("Task pack", str(task_pack.get("markdown", ""))),
        ("Evidence Markdown", evidence_markdown),
    )
    for export_name, markdown in exports:
        markdown_lines = set(markdown.splitlines())
        for expected_line, description in expected_lines:
            assert_condition(
                expected_line in markdown_lines,
                f"{export_name} is missing {description}.",
            )
    return readiness


def client_json(
    client, method: str, path: str, payload: dict | None = None
) -> dict | list:
    response = client.request(method, path, json=payload)
    if response.status_code >= 400:
        raise SmokeError(
            f"{method} {path} failed with HTTP {response.status_code}: {response.text}"
        )
    return response.json()


def check_result(checked: bool | None) -> str:
    if checked is None:
        return "skipped"
    return "passed" if checked else "failed"


def check_evidence(checked: bool | None, passed_text: str) -> str:
    if checked is None:
        return "not requested"
    return passed_text if checked else "failed before report generation"


def report_value(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def git_output(args: list[str], *, cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def repository_revision(root: Path = ROOT) -> str:
    commit = git_output(["rev-parse", "--short=12", "HEAD"], cwd=root)
    if not commit:
        return "unavailable"

    branch = git_output(["branch", "--show-current"], cwd=root) or "detached HEAD"
    status = git_output(["status", "--porcelain"], cwd=root)
    if status is None:
        tree_state = "working tree state unknown"
    elif status:
        tree_state = "local changes present"
    else:
        tree_state = "clean"
    return f"{branch} @ {commit} ({tree_state})"


def source_breakdown_rows(source_breakdown: object) -> list[str]:
    if not isinstance(source_breakdown, list) or not source_breakdown:
        return ["| No source breakdown returned | 0 |"]

    rows: list[str] = []
    for entry in sorted(
        source_breakdown,
        key=lambda item: str(item.get("source", "")) if isinstance(item, dict) else "",
    ):
        if not isinstance(entry, dict):
            continue
        rows.append(
            f"| {report_value(entry.get('source', 'unknown'))} | "
            f"{report_value(entry.get('count', 0))} |"
        )
    return rows or ["| No source breakdown returned | 0 |"]


def source_breakdown_summary(source_breakdown: object) -> list[dict[str, object]]:
    if not isinstance(source_breakdown, list):
        return []

    rows: list[dict[str, object]] = []
    for entry in sorted(
        source_breakdown,
        key=lambda item: str(item.get("source", "")) if isinstance(item, dict) else "",
    ):
        if not isinstance(entry, dict):
            continue
        rows.append(
            {
                "source": report_value(entry.get("source", "unknown")),
                "count": entry.get("count", 0),
            }
        )
    return rows


def check_task_pack_contract(markdown: str) -> int:
    if not TASK_PACK_CHECKER_PATH.exists():
        raise SmokeError(f"Task-pack checker is missing: {TASK_PACK_CHECKER_PATH}")

    spec = importlib.util.spec_from_file_location(
        "tasksignal_task_pack_checker",
        TASK_PACK_CHECKER_PATH,
    )
    if not spec or not spec.loader:
        raise SmokeError(
            f"Task-pack checker could not be loaded: {TASK_PACK_CHECKER_PATH}"
        )

    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    required_sections = getattr(checker, "REQUIRED_SECTIONS", None)
    structure_errors = getattr(checker, "task_pack_structure_errors", None)
    if not isinstance(required_sections, list) or not callable(structure_errors):
        raise SmokeError(
            "Task-pack checker does not expose the expected validation contract."
        )

    errors = [str(error) for error in structure_errors(markdown)]
    if errors:
        raise SmokeError(
            "Task-pack markdown failed structure check: " + "; ".join(errors)
        )
    return len(required_sections)


def proof_summary(
    result: dict[str, object],
    *,
    dashboard_source_checked: bool | None,
    live_dashboard_checked: bool | None,
    revision: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    timestamp = (generated_at or datetime.now(UTC)).replace(microsecond=0).isoformat()
    return {
        "generated_at": timestamp,
        "repository_revision": revision or "unavailable",
        "scope": "credential-free fixture smoke run against a temporary SQLite database",
        "checks": {
            "api_health": {
                "result": "passed",
                "evidence": {"status": result["health_status"]},
            },
            "readiness_endpoint": {
                "result": "passed",
                "evidence": {"status": result["readiness_status"]},
            },
            "fixture_demo_processing": {
                "result": "passed",
                "evidence": {
                    "raw_items_loaded": result["raw_items_loaded"],
                    "normalized_items_created": result["normalized_items_created"],
                    "signals_detected": result["signals_detected"],
                    "clusters_created": result["clusters_created"],
                    "opportunities_created": result["opportunities_created"],
                },
            },
            "stats_endpoint": {
                "result": "passed",
                "evidence": {
                    "total_items": result["total_items"],
                    "opportunities": result["stats_opportunities"],
                },
            },
            "task_pack_export": {
                "result": "passed",
                "evidence": {
                    "top_opportunity_id": result["top_opportunity_id"],
                    "top_opportunity": result["top_opportunity"],
                    "evidence_urls": result["task_pack_evidence_urls"],
                },
            },
            "task_pack_structure": {
                "result": "passed",
                "evidence": {
                    "required_sections": result["task_pack_required_sections"],
                    "validator": "skills/tasksignal-opportunity-builder/scripts/check_task_pack.py",
                },
            },
            "decision_review_workflow": {
                "result": "passed",
                "evidence": {
                    "review_state": result["decision_review_state"],
                    "evidence_reviews": result["evidence_reviews"],
                    "reviewed_items_before": result["evaluation_reviewed_items_before"],
                    "reviewed_items": result["evaluation_reviewed_items"],
                    "review_coverage_before": result[
                        "evaluation_review_coverage_before"
                    ],
                    "review_coverage": result["evaluation_review_coverage"],
                    "task_pack_readiness": result["task_pack_readiness"],
                    "local_notes_exported": False,
                },
            },
            "dashboard_route_source": {
                "result": check_result(dashboard_source_checked),
                "evidence": check_evidence(
                    dashboard_source_checked,
                    "route imports the dashboard feature",
                ),
            },
            "live_dashboard_request": {
                "result": check_result(live_dashboard_checked),
                "evidence": check_evidence(
                    live_dashboard_checked, "/dashboard returned HTML"
                ),
            },
        },
        "source_breakdown": source_breakdown_summary(result.get("source_breakdown")),
        "top_opportunity": {
            "id": result["top_opportunity_id"],
            "title": result["top_opportunity"],
        },
        "runtime_boundaries": {
            "llm_provider": result["llm_provider"],
            "public_scan_sources": result["public_scan_sources"],
            "database": "temporary SQLite file created for this smoke run",
            "omitted": [
                "secret values",
                "raw connector payloads",
                "local database paths",
                "private scan data",
            ],
        },
    }


def proof_report_markdown(
    result: dict[str, object],
    *,
    dashboard_source_checked: bool | None,
    live_dashboard_checked: bool | None,
    revision: str | None = None,
    generated_at: datetime | None = None,
) -> str:
    timestamp = (generated_at or datetime.now(UTC)).replace(microsecond=0).isoformat()
    lines = [
        "# TaskSignal First-Run Proof",
        "",
        f"Generated: {timestamp}",
        f"Repository revision: {report_value(revision or 'unavailable')}",
        "",
        "Scope: credential-free fixture smoke run against a temporary SQLite database.",
        "",
        "## Checks",
        "",
        "| Check | Result | Evidence |",
        "| --- | --- | --- |",
        f"| API health | passed | status={report_value(result['health_status'])} |",
        f"| Readiness endpoint | passed | status={report_value(result['readiness_status'])} |",
        (
            "| Fixture demo processing | passed | "
            f"{result['raw_items_loaded']} raw records, "
            f"{result['normalized_items_created']} normalized records, "
            f"{result['signals_detected']} signals, "
            f"{result['clusters_created']} clusters, "
            f"{result['opportunities_created']} opportunities |"
        ),
        (
            "| Stats endpoint | passed | "
            f"{result['total_items']} total items, "
            f"{result['stats_opportunities']} opportunities |"
        ),
        (
            "| Task-pack export | passed | "
            f"{result['task_pack_evidence_urls']} evidence URL(s) on the top opportunity |"
        ),
        (
            "| Task-pack structure | passed | "
            f"{result['task_pack_required_sections']} required sections present, "
            "validated by `skills/tasksignal-opportunity-builder/scripts/check_task_pack.py` |"
        ),
        (
            "| Decision review workflow | passed | "
            f"state={result['decision_review_state']}, "
            f"{result['evidence_reviews']} reviewed evidence item, "
            f"reviewed items={result['evaluation_reviewed_items_before']}"
            f"->{result['evaluation_reviewed_items']}, "
            f"coverage={result['evaluation_review_coverage_before']:.0%}"
            f"->{result['evaluation_review_coverage']:.0%}, "
            f"readiness={result['task_pack_readiness']}, local notes excluded |"
        ),
        (
            "| Dashboard route source | "
            f"{check_result(dashboard_source_checked)} | "
            f"{check_evidence(dashboard_source_checked, 'route imports the dashboard feature')} |"
        ),
        (
            "| Live dashboard request | "
            f"{check_result(live_dashboard_checked)} | "
            f"{check_evidence(live_dashboard_checked, '/dashboard returned HTML')} |"
        ),
        "",
        "## Source Mix",
        "",
        "| Source | Count |",
        "| --- | ---: |",
        *source_breakdown_rows(result.get("source_breakdown")),
        "",
        "## Top Opportunity",
        "",
        f"- {report_value(result['top_opportunity'])}",
        "",
        "## Runtime Boundaries",
        "",
        f"- LLM_PROVIDER={report_value(result['llm_provider'])}",
        f"- PUBLIC_SCAN_SOURCES={report_value(result['public_scan_sources'])}",
        "- Database: temporary SQLite file created for this smoke run.",
        "- Secrets, raw connector payloads, local database paths, and private scan data are omitted.",
        "",
        "## Follow-Up",
        "",
        "- For UI confidence, rerun with `--with-web-server` so the script boots Next.js and requests `/dashboard`.",
        "- For release evidence, pair this proof with `make release-check` and the relevant GitHub Actions run URL.",
        "",
    ]
    return "\n".join(lines)


def write_proof_report(path: Path, report: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def proof_bundle_manifest(
    path: Path,
    summary: dict[str, object],
    artifact_names: list[str],
) -> dict[str, object]:
    return {
        "generated_at": summary["generated_at"],
        "repository_revision": summary["repository_revision"],
        "files": [
            {
                "path": name,
                "bytes": (path / name).stat().st_size,
                "sha256": file_sha256(path / name),
            }
            for name in artifact_names
        ],
    }


def proof_bundle_manifest_errors(path: Path) -> list[str]:
    if not path.exists():
        return [f"Proof bundle directory is missing: {path}"]
    if not path.is_dir():
        return [f"Proof bundle path is not a directory: {path}"]

    manifest_path = path / PROOF_BUNDLE_MANIFEST
    if not manifest_path.exists():
        return [f"Proof bundle manifest is missing: {manifest_path}"]
    if not manifest_path.is_file():
        return [f"Proof bundle manifest is not a file: {manifest_path}"]

    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Proof bundle manifest is invalid JSON: {exc}"]

    if not isinstance(manifest, dict):
        return ["Proof bundle manifest must be a JSON object."]

    files = manifest.get("files")
    if not isinstance(files, list):
        return ["Proof bundle manifest must include a files list."]

    expected_artifacts = set(PROOF_BUNDLE_ARTIFACTS)
    seen_artifacts: set[str] = set()
    for index, entry in enumerate(files, start=1):
        if not isinstance(entry, dict):
            errors.append(f"manifest file entry {index} must be an object")
            continue

        artifact_name = entry.get("path")
        if not isinstance(artifact_name, str) or not artifact_name:
            errors.append(f"manifest file entry {index} has an invalid path")
            continue
        if Path(artifact_name).name != artifact_name:
            errors.append(f"manifest file entry {index} must use a top-level file path")
            continue
        if artifact_name == PROOF_BUNDLE_MANIFEST:
            errors.append("manifest must not list MANIFEST.json as an artifact")
            continue
        if artifact_name in seen_artifacts:
            errors.append(f"duplicate manifest file entry: {artifact_name}")
            continue

        seen_artifacts.add(artifact_name)
        artifact_path = path / artifact_name
        if not artifact_path.exists():
            errors.append(f"manifested file is missing: {artifact_name}")
            continue
        if not artifact_path.is_file():
            errors.append(f"manifested path is not a file: {artifact_name}")
            continue

        expected_bytes = entry.get("bytes")
        if not isinstance(expected_bytes, int) or expected_bytes < 0:
            errors.append(
                f"manifested bytes must be a non-negative integer: {artifact_name}"
            )
        elif artifact_path.stat().st_size != expected_bytes:
            errors.append(f"byte count mismatch for {artifact_name}")

        expected_sha256 = entry.get("sha256")
        if not isinstance(expected_sha256, str) or not expected_sha256:
            errors.append(
                f"manifested sha256 must be a non-empty string: {artifact_name}"
            )
        elif file_sha256(artifact_path) != expected_sha256:
            errors.append(f"sha256 mismatch for {artifact_name}")

    missing_entries = sorted(expected_artifacts - seen_artifacts)
    if missing_entries:
        errors.append(
            "manifest is missing generated artifact(s): " + ", ".join(missing_entries)
        )

    unexpected_manifest_entries = sorted(seen_artifacts - expected_artifacts)
    if unexpected_manifest_entries:
        errors.append(
            "manifest lists unexpected artifact(s): "
            + ", ".join(unexpected_manifest_entries)
        )

    unexpected_files = unexpected_proof_bundle_entries(path)
    if unexpected_files:
        errors.append(
            "proof bundle contains unexpected file(s): " + ", ".join(unexpected_files)
        )

    return errors


def verify_proof_bundle_manifest(path: Path) -> None:
    errors = proof_bundle_manifest_errors(path)
    if errors:
        raise SmokeError(
            "Proof bundle manifest verification failed: " + "; ".join(errors)
        )


def proof_bundle_readme(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# TaskSignal First-Run Proof Bundle",
            "",
            f"Generated: {report_value(summary['generated_at'])}",
            f"Repository revision: {report_value(summary['repository_revision'])}",
            "",
            "Files:",
            "",
            "- `first-run-proof.md`: human-readable smoke report.",
            "- `first-run-summary.json`: machine-readable counts, checks, and runtime boundaries.",
            (
                "- `top-opportunity-task-pack.md`: exact task pack exported for the top fixture "
                "opportunity and validated against the repo-local Codex skill contract."
            ),
            "- `MANIFEST.json`: file sizes and SHA-256 hashes for the generated artifacts.",
            "",
            (
                "This bundle is generated from fixture data only. It omits secret values, "
                "raw connector payloads, local database paths, and private scan data."
            ),
            "",
        ]
    )


def unexpected_proof_bundle_entries(path: Path) -> list[str]:
    if not path.exists():
        return []
    if not path.is_dir():
        raise SmokeError(f"Proof bundle path exists but is not a directory: {path}")

    expected = set(PROOF_BUNDLE_FILES)
    unexpected: list[str] = []
    for entry in path.iterdir():
        if entry.name not in expected:
            suffix = "/" if entry.is_dir() else ""
            unexpected.append(f"{entry.name}{suffix}")
    return sorted(unexpected)


def prepare_proof_bundle_dir(path: Path) -> None:
    unexpected = unexpected_proof_bundle_entries(path)
    if unexpected:
        raise SmokeError(
            "Proof bundle directory contains unexpected file(s): "
            + ", ".join(unexpected)
            + ". Use an empty directory or remove unrelated files before rerunning."
        )
    path.mkdir(parents=True, exist_ok=True)


def write_proof_bundle(
    path: Path,
    report: str,
    summary: dict[str, object],
    result: dict[str, object],
) -> None:
    prepare_proof_bundle_dir(path)
    artifact_names = PROOF_BUNDLE_ARTIFACTS
    write_proof_report(path / "README.md", proof_bundle_readme(summary))
    write_proof_report(path / "first-run-proof.md", report)
    (path / "first-run-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_proof_report(
        path / "top-opportunity-task-pack.md",
        f"{str(result['task_pack_markdown']).rstrip()}\n",
    )
    (path / "MANIFEST.json").write_text(
        json.dumps(
            proof_bundle_manifest(path, summary, artifact_names),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def run_api_checks(database_path: Path) -> dict[str, object]:
    os.environ.update(api_env(database_path))
    sys.path.insert(0, str(API_DIR))

    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated.*",
    )
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        health = client_json(client, "GET", "/health")
        api_readiness = client_json(client, "GET", "/api/readiness")
        summary = client_json(client, "POST", "/api/process/demo")
        stats = client_json(client, "GET", "/api/stats")
        opportunities = client_json(client, "GET", "/api/opportunities")

        assert_condition(isinstance(health, dict), "Health response was not an object.")
        assert_condition(
            health.get("status") == "ok", "Health endpoint did not return ok."
        )

        assert_condition(
            isinstance(api_readiness, dict), "Readiness response was not an object."
        )
        assert_condition(
            api_readiness.get("status") == "ready", "Readiness did not report ready."
        )

        assert_condition(
            isinstance(summary, dict), "Demo summary response was not an object."
        )
        assert_condition(
            summary.get("raw_items_loaded", 0) >= 17,
            "Demo loaded too few raw items.",
        )
        assert_condition(
            summary.get("signals_detected", 0) >= 15,
            "Demo detected too few signals.",
        )
        assert_condition(
            summary.get("opportunities_created", 0) >= 5,
            "Demo generated too few opportunities.",
        )

        assert_condition(isinstance(stats, dict), "Stats response was not an object.")
        assert_condition(stats.get("total_items", 0) >= 17, "Stats show too few items.")
        assert_condition(
            stats.get("opportunities", 0) >= 5, "Stats show too few opportunities."
        )

        assert_condition(
            isinstance(opportunities, list),
            "Opportunities response was not a list.",
        )
        assert_condition(
            len(opportunities) >= 5, "Opportunity list contains too few items."
        )
        first_opportunity = opportunities[0]
        assert_condition(
            isinstance(first_opportunity, dict) and first_opportunity.get("id"),
            "Top opportunity is missing an id.",
        )
        evidence_items = first_opportunity.get("evidence_items")
        assert_condition(
            isinstance(evidence_items, list) and evidence_items,
            "Top opportunity has no reviewable evidence.",
        )
        evidence_item = evidence_items[0]
        assert_condition(
            isinstance(evidence_item, dict) and evidence_item.get("id"),
            "Top evidence item is missing an id.",
        )
        opportunity_note = "SMOKE-LOCAL-OPPORTUNITY-NOTE-EXCLUDE"
        evidence_note = "SMOKE-LOCAL-EVIDENCE-NOTE-EXCLUDE"
        reviewed_opportunity = client_json(
            client,
            "PATCH",
            f"/api/opportunities/{first_opportunity['id']}/review",
            {"review_state": "promising", "review_note": opportunity_note},
        )
        baseline_evaluation = client_json(client, "GET", "/api/evaluation")
        evidence_review = client_json(
            client,
            "POST",
            "/api/labels",
            {
                "item_id": evidence_item["id"],
                "label": "true_signal",
                "user_note": evidence_note,
            },
        )
        evaluation = client_json(client, "GET", "/api/evaluation")
        assert_condition(
            isinstance(reviewed_opportunity, dict)
            and reviewed_opportunity.get("review_state") == "promising",
            "Opportunity decision did not persist.",
        )
        assert_condition(
            isinstance(evidence_review, dict)
            and evidence_review.get("label") == "true_signal",
            "Evidence review did not persist.",
        )
        assert_evaluation_review_progress(baseline_evaluation, evaluation)
        task_pack = client_json(
            client,
            "GET",
            f"/api/opportunities/{first_opportunity['id']}/task-pack.json",
        )
        assert_condition(
            isinstance(task_pack, dict), "Task-pack response was not an object."
        )
        assert_condition(
            str(task_pack.get("markdown", "")).startswith(
                "# TaskSignal Codex Task Pack:"
            ),
            "Task-pack markdown was not generated.",
        )
        assert_condition(
            task_pack.get("evidence_urls"), "Task-pack has no evidence URLs."
        )
        task_pack_required_sections = check_task_pack_contract(
            str(task_pack["markdown"])
        )
        evidence_response = client.get(
            f"/api/opportunities/{first_opportunity['id']}/evidence.md"
        )
        assert_condition(
            evidence_response.status_code == 200,
            "Evidence Markdown export failed.",
        )
        export_text = json.dumps(task_pack, sort_keys=True) + evidence_response.text
        readiness = assert_decision_export_context(task_pack, evidence_response.text)
        assert_condition(
            opportunity_note not in export_text and evidence_note not in export_text,
            "Local review notes leaked into an export.",
        )

        return {
            "health_status": health["status"],
            "readiness_status": api_readiness["status"],
            "raw_items_loaded": summary["raw_items_loaded"],
            "normalized_items_created": summary["normalized_items_created"],
            "signals_detected": summary["signals_detected"],
            "clusters_created": summary["clusters_created"],
            "opportunities_created": summary["opportunities_created"],
            "total_items": stats["total_items"],
            "stats_opportunities": stats["opportunities"],
            "source_breakdown": stats["source_breakdown"],
            "top_opportunity_id": first_opportunity["id"],
            "top_opportunity": first_opportunity["title"],
            "task_pack_evidence_urls": len(task_pack["evidence_urls"]),
            "task_pack_markdown": task_pack["markdown"],
            "task_pack_required_sections": task_pack_required_sections,
            "decision_review_state": reviewed_opportunity["review_state"],
            "evidence_reviews": 1,
            "evaluation_reviewed_items_before": baseline_evaluation["reviewed_items"],
            "evaluation_reviewed_items": evaluation["reviewed_items"],
            "evaluation_review_coverage_before": baseline_evaluation["review_coverage"],
            "evaluation_review_coverage": evaluation["review_coverage"],
            "task_pack_readiness": readiness["level"],
            "llm_provider": os.environ["LLM_PROVIDER"],
            "public_scan_sources": os.environ["PUBLIC_SCAN_SOURCES"],
        }


def run_dashboard_source_check() -> None:
    route_path = WEB_DIR / "src" / "app" / "dashboard" / "page.tsx"
    feature_path = WEB_DIR / "src" / "features" / "dashboard.tsx"
    assert_condition(route_path.exists(), "Dashboard route file is missing.")
    assert_condition(feature_path.exists(), "Dashboard feature file is missing.")

    route_text = route_path.read_text(encoding="utf-8")
    assert_condition(
        'from "@/features/dashboard"' in route_text,
        "Dashboard route is not wired to the dashboard feature.",
    )


def run_live_web_check(web_base: str) -> None:
    dashboard_html = request_text(f"{web_base}/dashboard")
    assert_condition(
        "<html" in dashboard_html.lower(), "Dashboard route did not return HTML."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a clean TaskSignal first-run smoke check against a temporary database."
    )
    parser.add_argument(
        "--api-timeout",
        type=int,
        default=60,
        help="Reserved for compatibility; API checks run in-process.",
    )
    parser.add_argument(
        "--web-timeout",
        type=int,
        default=90,
        help="Seconds to wait for the Next.js dashboard route.",
    )
    parser.add_argument(
        "--skip-web",
        action="store_true",
        help="Only smoke the API fixture flow and task-pack export.",
    )
    parser.add_argument(
        "--with-web-server",
        action="store_true",
        help="Also start Next.js and request /dashboard. This uses the native Next compiler.",
    )
    parser.add_argument(
        "--proof-out",
        type=Path,
        default=None,
        help="Write a Markdown proof report after all requested smoke checks pass.",
    )
    parser.add_argument(
        "--proof-dir",
        type=Path,
        default=None,
        help="Write a reviewer proof bundle directory after all requested smoke checks pass.",
    )
    parser.add_argument(
        "--verify-proof-dir",
        type=Path,
        default=None,
        help="Verify an existing proof bundle manifest and exit without rerunning smoke checks.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.verify_proof_dir:
        try:
            verify_proof_bundle_manifest(args.verify_proof_dir)
        except SmokeError as exc:
            print(f"[FAIL] {exc}", file=sys.stderr)
            return 1
        print(
            f"[OK] Proof bundle manifest verified: {args.verify_proof_dir}", flush=True
        )
        return 0

    processes: list[ManagedProcess] = []
    temp_dir = Path(tempfile.mkdtemp(prefix="tasksignal-smoke-"))
    passed = False
    api_base = "http://127.0.0.1:8000"
    dashboard_source_checked: bool | None = None
    live_dashboard_checked: bool | None = None

    try:
        result = run_api_checks(temp_dir / "tasksignal-smoke.db")
        print("[OK] API fixture endpoints passed with a temporary database", flush=True)
        print(
            "[OK] Fixture flow: "
            f"{result['raw_items_loaded']} raw items, "
            f"{result['signals_detected']} signals, "
            f"{result['opportunities_created']} opportunities",
            flush=True,
        )
        print(f"[OK] Task-pack export: {result['top_opportunity']}", flush=True)
        print(
            "[OK] Decision workflow: "
            f"{result['decision_review_state']}, "
            f"{result['evidence_reviews']} evidence review, "
            "local notes excluded",
            flush=True,
        )

        if not args.skip_web:
            run_dashboard_source_check()
            dashboard_source_checked = True
            print("[OK] Dashboard route source is wired", flush=True)

        if args.with_web_server and not args.skip_web:
            web_port = free_port()
            web_base = f"http://127.0.0.1:{web_port}"
            next_bin = WEB_DIR / "node_modules" / ".bin" / "next"
            if not next_bin.exists():
                raise SmokeError(
                    "apps/web/node_modules/.bin/next is missing; run npm install in apps/web."
                )
            web = start_process(
                "web",
                [
                    str(next_bin),
                    "dev",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    str(web_port),
                ],
                cwd=WEB_DIR,
                env=web_env(api_base),
                log_dir=temp_dir,
            )
            processes.append(web)

            def check_dashboard() -> None:
                exit_code = web.process.poll()
                if exit_code is not None:
                    raise SmokeError(
                        "Web process exited before the dashboard loaded "
                        f"(exit {exit_code}). Last log lines:\n{tail_log(web.log_path)}"
                    )
                run_live_web_check(web_base)

            wait_for(
                "Web dashboard",
                check_dashboard,
                timeout=args.web_timeout,
            )
            live_dashboard_checked = True
            print(f"[OK] Dashboard route loaded at {web_base}/dashboard", flush=True)

        if args.proof_out or args.proof_dir:
            generated_at = datetime.now(UTC)
            revision = repository_revision()
            report = proof_report_markdown(
                result,
                dashboard_source_checked=dashboard_source_checked,
                live_dashboard_checked=live_dashboard_checked,
                revision=revision,
                generated_at=generated_at,
            )
            summary = proof_summary(
                result,
                dashboard_source_checked=dashboard_source_checked,
                live_dashboard_checked=live_dashboard_checked,
                revision=revision,
                generated_at=generated_at,
            )
            if args.proof_out:
                write_proof_report(args.proof_out, report)
                print(f"[OK] Proof report written to {args.proof_out}", flush=True)
            if args.proof_dir:
                write_proof_bundle(args.proof_dir, report, summary, result)
                print(f"[OK] Proof bundle written to {args.proof_dir}", flush=True)
        passed = True

    except SmokeError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        for managed in processes:
            print(
                f"[INFO] {managed.name} log: {managed.log_path}",
                file=sys.stderr,
            )
        return 1
    finally:
        for managed in reversed(processes):
            managed.stop()
        if passed:
            shutil.rmtree(temp_dir, ignore_errors=True)

    print("[OK] First-run smoke passed with a temporary database.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
