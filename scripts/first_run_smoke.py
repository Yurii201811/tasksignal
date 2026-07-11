#!/usr/bin/env python3
"""Credential-free first-run smoke check for TaskSignal."""

from __future__ import annotations

import argparse
import hashlib
import io
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
from uuid import UUID, uuid4
from urllib.error import URLError
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
WEB_DIR = ROOT / "apps" / "web"
FIXTURE_DIR = API_DIR / "app" / "resources" / "fixtures"
HOMEBREW_NODE20_BIN = Path("/opt/homebrew/opt/node@20/bin")
TASK_PACK_CHECKER_PATH = (
    ROOT
    / "skills"
    / "tasksignal-opportunity-builder"
    / "scripts"
    / "check_task_pack.py"
)
BUILD_PACKET_FILES = {
    "README.md",
    "MANIFEST.json",
    "opportunity.json",
    "evidence.md",
    "task-pack.md",
    "product-requirements.md",
    "validation-plan.md",
    "github-issue.md",
    "implementation-plan.md",
    "agent-brief.md",
}
BUILD_PACKET_SCHEMA_VERSION = "tasksignal.build-packet/v1"
BUILD_PACKET_TEMPLATE_VERSION = "deterministic-v1"
BUILD_PACKET_MANIFEST_SELF_HASH_POLICY = (
    "MANIFEST.json is excluded to avoid recursive self-hashing; "
    "persist the manifest immutably with the packet record."
)
BUILD_PACKET_UUID_FIELDS = (
    "packet_id",
    "project_id",
    "run_id",
    "thread_id",
    "snapshot_id",
    "decision_event_id",
)
BUILD_PACKET_SHA256_FIELDS = ("source_snapshot_sha256", "decision_sha256")
PRIVACY_MARKER_CATEGORIES = (
    "local_notes",
    "raw_identities",
    "author_hashes",
    "secret_values",
)
PROOF_BUNDLE_SCHEMA_VERSION = "tasksignal.first-run-proof/v1"
PROOF_BUNDLE_ARTIFACTS = [
    "README.md",
    "first-run-proof.md",
    "first-run-summary.json",
    "top-opportunity-task-pack.md",
    "top-opportunity-build-packet.zip",
    "top-opportunity-build-packet-manifest.json",
    "top-opportunity-build-packet-verification.json",
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
            "OPERATOR_SCAN_TOKEN": "first-run-smoke-operator-only",
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
    client,
    method: str,
    path: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> dict | list:
    response = client.request(method, path, json=payload, headers=headers)
    if response.status_code >= 400:
        raise SmokeError(
            f"{method} {path} failed with HTTP {response.status_code}: {response.text}"
        )
    return response.json()


def fixture_raw_identity_markers(
    fixture_dir: Path,
    selected_identities: set[tuple[str, str]],
) -> set[str]:
    """Read raw author identities before the scan pipeline sanitizes fixture payloads."""

    markers: set[str] = set()
    observed: set[tuple[str, str]] = set()
    try:
        paths = sorted(fixture_dir.glob("*_sample.json"))
    except OSError as exc:
        raise SmokeError("Fixture inputs could not be enumerated.") from exc
    assert_condition(paths, "Fixture inputs are missing from the source checkout.")

    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SmokeError(
                "A pre-sanitized fixture input could not be read."
            ) from exc
        if not isinstance(payload, dict):
            raise SmokeError("A pre-sanitized fixture input was not an object.")
        source = str(payload.get("source") or path.stem.replace("_sample", ""))
        items = payload.get("items")
        if not isinstance(items, list):
            raise SmokeError("A pre-sanitized fixture input omitted its items list.")
        for item in items:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get("external_id") or item.get("id") or "")
            identity = (source, external_id)
            if identity not in selected_identities:
                continue
            observed.add(identity)
            candidates = [item.get("author"), item.get("by"), item.get("username")]
            user = item.get("user")
            if isinstance(user, dict):
                candidates.append(user.get("login"))
            owner = item.get("owner")
            if isinstance(owner, dict):
                candidates.append(owner.get("display_name"))
            markers.update(
                value for value in candidates if isinstance(value, str) and value
            )

    missing = selected_identities - observed
    assert_condition(
        not missing,
        f"Pre-sanitized fixture inputs omitted {len(missing)} selected evidence item(s).",
    )
    assert_condition(
        markers,
        "Pre-sanitized fixture inputs exposed no raw identity markers to verify.",
    )
    return markers


def privacy_marker_categories(
    *,
    local_notes: set[str],
    raw_identities: set[str],
    author_hashes: set[str],
    runtime_secrets: set[str],
) -> dict[str, set[str]]:
    categories = {
        "local_notes": set(local_notes),
        "raw_identities": set(raw_identities),
        "author_hashes": set(author_hashes),
        "secret_values": set(runtime_secrets),
    }
    assert_condition(
        all(categories.values()),
        "Build-packet privacy proof contained an empty marker category.",
    )
    return categories


def assert_identical_run_delta(
    delta: object,
    *,
    observed_items: int,
    signal_items: int,
    opportunity_threads: int,
) -> None:
    assert_condition(isinstance(delta, dict), "Run delta response was not an object.")
    if not isinstance(delta, dict):  # pragma: no cover - narrowed above.
        return
    expected_evidence = {
        "new": 0,
        "seen_before": observed_items,
        "updated": 0,
        "unchanged": observed_items,
        "not_observed_this_run": 0,
    }
    expected_opportunities = {
        "new": 0,
        "updated": 0,
        "unchanged": opportunity_threads,
        "not_observed_this_run": 0,
    }
    expected_signals = {
        **expected_evidence,
        "seen_before": signal_items,
        "unchanged": signal_items,
    }
    assert_condition(
        delta.get("evidence_changes") == expected_evidence,
        "Identical project run did not report the precise zero-new evidence delta: "
        f"{delta.get('evidence_changes')!r}.",
    )
    assert_condition(
        delta.get("signal_changes") == expected_signals,
        "Identical project run did not report the precise zero-new signal delta: "
        f"{delta.get('signal_changes')!r}.",
    )
    assert_condition(
        delta.get("opportunity_changes") == expected_opportunities,
        "Identical project run reported a false new or changed opportunity thread: "
        f"{delta.get('opportunity_changes')!r}.",
    )
    serialized = json.dumps(delta, sort_keys=True).lower()
    assert_condition(
        "deleted" not in serialized and "resolved" not in serialized,
        "Run delta used deletion or resolution language for absent evidence.",
    )


def packet_manifest_content(packet: dict[str, object]) -> str:
    artifact = next(
        (
            entry
            for entry in packet.get("artifacts", [])
            if isinstance(entry, dict) and entry.get("path") == "MANIFEST.json"
        ),
        None,
    )
    assert_condition(isinstance(artifact, dict), "Build packet omitted MANIFEST.json.")
    if not isinstance(artifact, dict):  # pragma: no cover - narrowed above.
        return ""
    return str(artifact.get("content", ""))


def inspect_build_packet(
    packet: object,
    archive_bytes: bytes,
    verification: object,
    *,
    forbidden_marker_categories: dict[str, set[str]],
) -> dict[str, object]:
    assert_condition(
        isinstance(packet, dict), "Build packet response was not an object."
    )
    assert_condition(
        isinstance(verification, dict),
        "Build packet verification response was not an object.",
    )
    if not isinstance(packet, dict) or not isinstance(verification, dict):
        return {}  # pragma: no cover - narrowed above.

    artifacts = packet.get("artifacts")
    assert_condition(
        isinstance(artifacts, list), "Build packet artifacts were not a list."
    )
    if not isinstance(artifacts, list):  # pragma: no cover - narrowed above.
        return {}
    by_path = {
        str(entry.get("path")): entry for entry in artifacts if isinstance(entry, dict)
    }
    assert_condition(
        set(by_path) == BUILD_PACKET_FILES,
        "Build packet did not contain exactly the required 10 files.",
    )
    for path, entry in by_path.items():
        content = str(entry.get("content", ""))
        content_bytes = content.encode("utf-8")
        assert_condition(content_bytes, f"Build packet artifact is empty: {path}.")
        assert_condition(
            entry.get("byte_count") == len(content_bytes),
            f"Build packet byte count mismatch: {path}.",
        )
        assert_condition(
            entry.get("sha256") == hashlib.sha256(content_bytes).hexdigest(),
            f"Build packet SHA-256 mismatch: {path}.",
        )

    manifest_content = str(by_path["MANIFEST.json"].get("content", ""))
    try:
        manifest = json.loads(manifest_content)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"Build packet MANIFEST.json was invalid: {exc}") from exc
    assert_condition(
        manifest == packet.get("manifest"), "Packet manifest payloads differ."
    )
    assert_condition(
        manifest.get("file_count") == len(BUILD_PACKET_FILES),
        "Build packet manifest did not record 10 files.",
    )
    assert_condition(
        manifest.get("generation_mode") == "deterministic",
        "Build packet was not generated deterministically.",
    )
    assert_condition(
        manifest.get("deterministic_originals_authoritative") is True,
        "Build packet did not mark deterministic originals authoritative.",
    )
    expected_metadata = {
        "packet_id": str(packet.get("id")),
        "project_id": str(packet.get("project_id")),
        "run_id": str(packet.get("run_id")),
        "thread_id": str(packet.get("thread_id")),
        "snapshot_id": str(packet.get("snapshot_id")),
        "schema_version": packet.get("schema_version"),
        "tasksignal_version": packet.get("tasksignal_version"),
        "template_version": packet.get("template_version"),
        "generation_mode": packet.get("generation_mode"),
    }
    for key, expected in expected_metadata.items():
        assert_condition(
            manifest.get(key) == expected,
            f"Build packet manifest metadata mismatch: {key}.",
        )

    manifest_files = manifest.get("files")
    assert_condition(
        isinstance(manifest_files, list),
        "Build packet manifest files entry was not a list.",
    )
    if not isinstance(manifest_files, list):  # pragma: no cover - narrowed above.
        return {}
    manifested_paths = {
        str(entry.get("path")) for entry in manifest_files if isinstance(entry, dict)
    }
    assert_condition(
        manifested_paths == BUILD_PACKET_FILES - {"MANIFEST.json"},
        "Build packet manifest inventory did not match authoritative artifacts.",
    )
    for entry in manifest_files:
        assert_condition(
            isinstance(entry, dict), "Invalid build packet manifest entry."
        )
        if not isinstance(entry, dict):  # pragma: no cover - narrowed above.
            continue
        artifact = by_path[str(entry.get("path"))]
        assert_condition(
            entry.get("bytes") == artifact.get("byte_count")
            and entry.get("sha256") == artifact.get("sha256"),
            f"Build packet manifest hash metadata mismatch: {entry.get('path')}.",
        )
    assert_condition(
        packet.get("manifest_sha256")
        == hashlib.sha256(manifest_content.encode("utf-8")).hexdigest()
        == by_path["MANIFEST.json"].get("sha256"),
        "Build packet MANIFEST.json hash mismatch.",
    )

    assert_condition(
        verification.get("valid") is True, "Server packet verification failed."
    )
    for field in ("errors", "missing_files", "unexpected_files", "mismatched_files"):
        assert_condition(
            verification.get(field) == [],
            f"Server packet verification reported {field}.",
        )

    with ZipFile(io.BytesIO(archive_bytes)) as archive:
        names = archive.namelist()
        assert_condition(
            names == sorted(BUILD_PACKET_FILES),
            "Downloaded packet archive inventory was not deterministic and complete.",
        )
        for name in names:
            assert_condition(
                archive.read(name)
                == str(by_path[name].get("content", "")).encode("utf-8"),
                f"Downloaded packet artifact differed from its immutable record: {name}.",
            )
        assert_condition(
            all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()),
            "Downloaded packet archive timestamps were not deterministic.",
        )

    assert_condition(
        set(forbidden_marker_categories) == set(PRIVACY_MARKER_CATEGORIES),
        "Build-packet privacy marker categories were incomplete.",
    )
    marker_counts = {
        category: len(markers)
        for category, markers in sorted(forbidden_marker_categories.items())
    }
    assert_condition(
        all(count > 0 for count in marker_counts.values()),
        "Build-packet privacy proof contained an empty marker category.",
    )
    serialized = "\n".join(
        str(by_path[name].get("content", "")) for name in sorted(by_path)
    )
    leaked_categories = {
        category: sum(marker in serialized for marker in markers)
        for category, markers in forbidden_marker_categories.items()
    }
    assert_condition(
        not any(leaked_categories.values()),
        "Build packet leaked private marker(s) in category count(s): "
        + ", ".join(
            f"{category}={count}"
            for category, count in sorted(leaked_categories.items())
            if count
        ),
    )
    unique_markers = set().union(*forbidden_marker_categories.values())
    return {
        "artifact_count": len(by_path),
        "manifested_original_count": len(manifested_paths),
        "archive_bytes": len(archive_bytes),
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "private_markers_checked": len(unique_markers),
        "private_marker_counts": marker_counts,
        "privacy_exports": {
            f"{category}_exported": False for category in PRIVACY_MARKER_CATEGORIES
        },
    }


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
            "longitudinal_research_memory": {
                "result": "passed",
                "evidence": {
                    "project_runs": result["project_runs"],
                    "observed_items": result["identical_run_seen_before"],
                    "new_evidence_on_identical_run": result[
                        "identical_run_new_evidence"
                    ],
                    "unchanged_evidence_on_identical_run": result[
                        "identical_run_unchanged"
                    ],
                    "threads_after_first_run": result["threads_after_first_run"],
                    "threads_after_second_run": result["threads_after_second_run"],
                    "automatically_matched_threads": result[
                        "automatically_matched_threads"
                    ],
                    "false_new_threads": result["false_new_threads"],
                    "match_method": "exact_evidence",
                    "match_confidence": 1.0,
                },
            },
            "actor_aware_evidence_review": {
                "result": "passed",
                "evidence": {
                    "human_labels": result["human_labels"],
                    "agent_labels": result["agent_labels"],
                    "human_label_visible": result["human_label_visible"],
                    "agent_label_visible": result["agent_label_visible"],
                    "agent_session_provenance": result["agent_session_provenance"],
                    "human_precision_before_agent_label": result[
                        "human_precision_before_agent_label"
                    ],
                    "human_precision_after_agent_label": result[
                        "human_precision_after_agent_label"
                    ],
                    "readiness_before_agent_label": result[
                        "readiness_before_agent_label"
                    ],
                    "readiness_after_agent_label": result[
                        "readiness_after_agent_label"
                    ],
                    "agent_self_grading_excluded": True,
                },
            },
            "immutable_build_packet": {
                "result": "passed",
                "evidence": {
                    "review_state": result["build_candidate_state"],
                    "generation_mode": result["build_packet_generation_mode"],
                    "artifact_count": result["build_packet_artifact_count"],
                    "manifested_original_count": result[
                        "build_packet_manifested_original_count"
                    ],
                    "archive_bytes": result["build_packet_archive_byte_count"],
                    "archive_sha256": result["build_packet_archive_sha256"],
                    "server_verified": result["build_packet_server_verified"],
                    "repeat_download_identical": result[
                        "build_packet_repeat_download_identical"
                    ],
                    "immutable_fetch_identical": result[
                        "build_packet_immutable_fetch_identical"
                    ],
                },
            },
            "build_packet_privacy": {
                "result": "passed",
                "evidence": {
                    "private_markers_checked": result[
                        "build_packet_private_markers_checked"
                    ],
                    "marker_counts": result["build_packet_private_marker_counts"],
                    **result["build_packet_privacy_exports"],
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
            f"{result['evidence_reviews']} reviewed evidence "
            f"{'item' if result['evidence_reviews'] == 1 else 'items'}, "
            f"reviewed items={result['evaluation_reviewed_items_before']}"
            f"->{result['evaluation_reviewed_items']}, "
            f"coverage={result['evaluation_review_coverage_before']:.0%}"
            f"->{result['evaluation_review_coverage']:.0%}, "
            f"readiness={result['task_pack_readiness']}, local notes excluded |"
        ),
        (
            "| Longitudinal research memory | passed | "
            f"{result['project_runs']} runs, identical rerun: "
            f"new={result['identical_run_new_evidence']}, "
            f"seen before={result['identical_run_seen_before']}, "
            f"updated=0, unchanged={result['identical_run_unchanged']}, "
            "not observed=0; "
            f"threads={result['threads_after_first_run']}"
            f"->{result['threads_after_second_run']}, "
            f"exact matches={result['automatically_matched_threads']}, "
            f"false new threads={result['false_new_threads']} |"
        ),
        (
            "| Actor-aware evidence review | passed | "
            f"human labels={result['human_labels']}, agent labels={result['agent_labels']}, "
            f"human precision={result['human_precision_before_agent_label']}"
            f"->{result['human_precision_after_agent_label']}, "
            f"readiness={result['readiness_before_agent_label']}"
            f"->{result['readiness_after_agent_label']}; agent self-grading excluded |"
        ),
        (
            "| Immutable build packet | passed | "
            f"state={result['build_candidate_state']}, "
            f"mode={result['build_packet_generation_mode']}, "
            f"files={result['build_packet_artifact_count']}, "
            f"archive bytes={result['build_packet_archive_byte_count']}, "
            f"server verified={str(result['build_packet_server_verified']).lower()}, "
            "repeat download identical |"
        ),
        (
            "| Build-packet privacy | passed | "
            f"{result['build_packet_private_markers_checked']} private markers checked; "
            f"categories={report_value(result['build_packet_private_marker_counts'])}; "
            "local notes, raw identities, author hashes, and secret values excluded |"
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
        "schema_version": PROOF_BUNDLE_SCHEMA_VERSION,
        "generated_at": summary["generated_at"],
        "repository_revision": summary["repository_revision"],
        "artifact_count": len(artifact_names),
        "files": [
            {
                "path": name,
                "bytes": (path / name).stat().st_size,
                "sha256": file_sha256(path / name),
            }
            for name in artifact_names
        ],
    }


def _canonical_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _lower_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def build_packet_manifest_contract_errors(manifest: object) -> list[str]:
    if not isinstance(manifest, dict):
        return ["build packet manifest must be a JSON object"]

    required = {
        "schema_version",
        "tasksignal_version",
        "template_version",
        *BUILD_PACKET_UUID_FIELDS,
        "generated_at",
        "generation_mode",
        "deterministic_originals_authoritative",
        "lineage_status",
        *BUILD_PACKET_SHA256_FIELDS,
        "manifest_self_hash",
        "manifest_self_hash_policy",
        "enhancement",
        "file_count",
        "files",
    }
    errors: list[str] = []
    missing = sorted(required - set(manifest))
    if missing:
        errors.append(
            "build packet manifest missing required metadata: " + ", ".join(missing)
        )

    if manifest.get("schema_version") != BUILD_PACKET_SCHEMA_VERSION:
        errors.append(
            f"build packet schema_version must be {BUILD_PACKET_SCHEMA_VERSION}"
        )
    version = manifest.get("tasksignal_version")
    if not isinstance(version, str) or not version or version != version.strip():
        errors.append("build packet tasksignal_version must be a non-empty string")
    if manifest.get("template_version") != BUILD_PACKET_TEMPLATE_VERSION:
        errors.append(
            f"build packet template_version must be {BUILD_PACKET_TEMPLATE_VERSION}"
        )
    for field in BUILD_PACKET_UUID_FIELDS:
        if not _canonical_uuid(manifest.get(field)):
            errors.append(f"build packet {field} must be a canonical UUID")
    generated_at = manifest.get("generated_at")
    try:
        parsed_generated_at = datetime.fromisoformat(
            str(generated_at).replace("Z", "+00:00")
        )
    except ValueError:
        parsed_generated_at = None
    if (
        not isinstance(generated_at, str)
        or not generated_at.endswith("Z")
        or parsed_generated_at is None
        or parsed_generated_at.utcoffset()
        != datetime.min.replace(tzinfo=UTC).utcoffset()
    ):
        errors.append("build packet generated_at must be an ISO-8601 UTC timestamp")
    if manifest.get("generation_mode") != "deterministic":
        errors.append("build packet generation_mode must be deterministic")
    if manifest.get("deterministic_originals_authoritative") is not True:
        errors.append("build packet deterministic originals must be authoritative")
    if manifest.get("lineage_status") != "complete":
        errors.append("build packet lineage_status must be complete")
    for field in BUILD_PACKET_SHA256_FIELDS:
        if not _lower_sha256(manifest.get(field)):
            errors.append(f"build packet {field} must be a lowercase SHA-256")
    if manifest.get("manifest_self_hash") is not None:
        errors.append("build packet manifest_self_hash must be null")
    if (
        manifest.get("manifest_self_hash_policy")
        != BUILD_PACKET_MANIFEST_SELF_HASH_POLICY
    ):
        errors.append("build packet manifest_self_hash_policy is invalid")
    if manifest.get("enhancement") != {
        "requested": False,
        "status": "not_requested",
        "provider": None,
        "model": None,
    }:
        errors.append("deterministic build packet enhancement metadata is invalid")
    if manifest.get("file_count") != len(BUILD_PACKET_FILES):
        errors.append(
            f"build packet manifest file_count must be {len(BUILD_PACKET_FILES)}"
        )
    return errors


def build_packet_archive_contract_errors(archive: ZipFile) -> list[str]:
    errors: list[str] = []
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if names != sorted(BUILD_PACKET_FILES):
        errors.append("build packet archive inventory must contain exactly 10 files")
        return errors
    for info in infos:
        if info.date_time != (1980, 1, 1, 0, 0, 0):
            errors.append(
                f"build packet file must use the deterministic timestamp: {info.filename}"
            )
        if info.compress_type != ZIP_DEFLATED:
            errors.append(
                f"build packet file must use DEFLATE compression: {info.filename}"
            )
        if info.create_system != 3:
            errors.append(
                f"build packet file must use the Unix creator system: {info.filename}"
            )
        if info.external_attr >> 16 != 0o100644:
            errors.append(
                f"build packet file must use 0644 regular-file mode: {info.filename}"
            )
        if info.flag_bits != 0 or info.extra or info.comment:
            errors.append(
                f"build packet file has nondeterministic ZIP metadata: {info.filename}"
            )
    if archive.comment:
        errors.append("build packet archive must not have a ZIP comment")
    return errors


def proof_summary_packet_errors(path: Path, packet_archive_path: Path) -> list[str]:
    summary_path = path / "first-run-summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        evidence = summary["checks"]["immutable_build_packet"]["evidence"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return ["first-run summary omitted immutable build packet evidence"]
    if not isinstance(evidence, dict):
        return ["first-run summary build packet evidence must be an object"]

    errors: list[str] = []
    archive_size = packet_archive_path.stat().st_size
    archive_sha256 = file_sha256(packet_archive_path)
    if evidence.get("archive_bytes") != archive_size:
        errors.append("first-run summary archive byte count does not match packet")
    if evidence.get("archive_sha256") != archive_sha256:
        errors.append("first-run summary archive sha256 does not match packet")
    if evidence.get("generation_mode") != "deterministic":
        errors.append("first-run summary generation mode is not deterministic")
    if evidence.get("artifact_count") != len(BUILD_PACKET_FILES):
        errors.append("first-run summary artifact count is not 10")
    if evidence.get("manifested_original_count") != len(BUILD_PACKET_FILES) - 1:
        errors.append("first-run summary manifested original count is not 9")
    if evidence.get("server_verified") is not True:
        errors.append("first-run summary did not record server verification")
    return errors


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

    if manifest.get("schema_version") != PROOF_BUNDLE_SCHEMA_VERSION:
        errors.append(
            "proof bundle manifest schema_version must be "
            f"{PROOF_BUNDLE_SCHEMA_VERSION}"
        )

    files = manifest.get("files")
    if not isinstance(files, list):
        return ["Proof bundle manifest must include a files list."]
    if manifest.get("artifact_count") != len(PROOF_BUNDLE_ARTIFACTS):
        errors.append(
            f"proof bundle manifest artifact_count must be {len(PROOF_BUNDLE_ARTIFACTS)}"
        )

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

    packet_archive_path = path / "top-opportunity-build-packet.zip"
    packet_manifest_path = path / "top-opportunity-build-packet-manifest.json"
    packet_verification_path = path / "top-opportunity-build-packet-verification.json"
    try:
        with ZipFile(packet_archive_path) as archive:
            errors.extend(build_packet_archive_contract_errors(archive))
            try:
                archived_manifest = archive.read("MANIFEST.json")
            except KeyError:
                archived_manifest = b""
            extracted_manifest = packet_manifest_path.read_bytes()
            if archived_manifest != extracted_manifest:
                errors.append(
                    "extracted build packet manifest differs from the archive"
                )
            try:
                packet_manifest = json.loads(archived_manifest)
            except json.JSONDecodeError as exc:
                errors.append(f"build packet manifest is invalid JSON: {exc}")
                packet_manifest = {}
            errors.extend(build_packet_manifest_contract_errors(packet_manifest))
            packet_files = (
                packet_manifest.get("files")
                if isinstance(packet_manifest, dict)
                else None
            )
            if not isinstance(packet_files, list):
                errors.append("build packet manifest must include a files list")
            else:
                manifested_packet_paths = {
                    str(entry.get("path"))
                    for entry in packet_files
                    if isinstance(entry, dict)
                }
                if len(packet_files) != len(manifested_packet_paths):
                    errors.append(
                        "build packet manifest contains duplicate file entries"
                    )
                if manifested_packet_paths != BUILD_PACKET_FILES - {"MANIFEST.json"}:
                    errors.append(
                        "build packet manifest inventory does not match the archive"
                    )
                for entry in packet_files:
                    if not isinstance(entry, dict):
                        errors.append(
                            "build packet manifest file entry must be an object"
                        )
                        continue
                    artifact_name = str(entry.get("path"))
                    try:
                        content = archive.read(artifact_name)
                    except KeyError:
                        errors.append(
                            f"manifested build packet file is missing: {artifact_name}"
                        )
                        continue
                    if entry.get("bytes") != len(content):
                        errors.append(
                            f"build packet byte count mismatch for {artifact_name}"
                        )
                    if entry.get("sha256") != hashlib.sha256(content).hexdigest():
                        errors.append(
                            f"build packet sha256 mismatch for {artifact_name}"
                        )
    except (BadZipFile, OSError, ValueError) as exc:
        errors.append(f"build packet archive is invalid: {exc}")

    try:
        errors.extend(proof_summary_packet_errors(path, packet_archive_path))
    except OSError as exc:
        errors.append(f"build packet summary cross-check failed: {exc}")

    try:
        packet_verification = json.loads(
            packet_verification_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"build packet verification evidence is invalid: {exc}")
    else:
        if (
            not isinstance(packet_verification, dict)
            or packet_verification.get("valid") is not True
        ):
            errors.append("build packet server verification did not report valid=true")
        elif any(
            packet_verification.get(field) != []
            for field in (
                "errors",
                "missing_files",
                "unexpected_files",
                "mismatched_files",
            )
        ):
            errors.append("build packet server verification reported integrity errors")

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
            (
                "- `top-opportunity-build-packet.zip`: deterministic immutable 10-file build "
                "packet downloaded twice with identical bytes."
            ),
            (
                "- `top-opportunity-build-packet-manifest.json`: the packet's exact immutable "
                "manifest, including byte counts and SHA-256 hashes."
            ),
            (
                "- `top-opportunity-build-packet-verification.json`: the successful server-side "
                "packet verification response."
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
    archive_bytes = result.get("build_packet_archive_bytes")
    assert_condition(
        isinstance(archive_bytes, bytes),
        "Build packet archive bytes are missing from the proof result.",
    )
    if isinstance(archive_bytes, bytes):
        (path / "top-opportunity-build-packet.zip").write_bytes(archive_bytes)
    write_proof_report(
        path / "top-opportunity-build-packet-manifest.json",
        f"{str(result['build_packet_manifest_content']).rstrip()}\n",
    )
    (path / "top-opportunity-build-packet-verification.json").write_text(
        json.dumps(
            result["build_packet_verification"],
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
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
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.main import app
    from app.models.all_models import NormalizedItem
    from app.services.agent_sessions import (
        STANDARD_WRITE_CAPABILITIES,
        hash_session_secret,
    )
    from app.services.evidence_review.service import append_evidence_label
    from app.services.evidence_review.types import EvidenceReviewLabel

    with TestClient(app) as client:
        health = client_json(client, "GET", "/health")
        api_readiness = client_json(client, "GET", "/api/v1/readiness")
        project = client_json(
            client,
            "POST",
            "/api/v1/research-projects",
            {
                "name": "First-run fixture workbench",
                "description": "Credential-free v1 evidence-to-build proof.",
                "source_type": "fixture",
                "query": "",
                "limit": 100,
                "cadence": "manual",
                "labels": ["first-run", "fixture"],
                "enabled": True,
            },
        )
        assert_condition(
            isinstance(project, dict), "Project response was not an object."
        )
        if not isinstance(project, dict):  # pragma: no cover - narrowed above.
            raise SmokeError("Project response was not an object.")
        first_run = client_json(
            client,
            "POST",
            f"/api/v1/research-projects/{project['id']}/run",
        )
        first_threads = client_json(
            client,
            "GET",
            f"/api/v1/opportunity-threads?project_id={project['id']}",
        )
        identical_run = client_json(
            client,
            "POST",
            f"/api/v1/research-projects/{project['id']}/run",
        )
        project_runs = client_json(
            client,
            "GET",
            f"/api/v1/research-projects/{project['id']}/runs",
        )
        second_threads = client_json(
            client,
            "GET",
            f"/api/v1/opportunity-threads?project_id={project['id']}",
        )
        stats = client_json(client, "GET", "/api/stats")

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
            isinstance(first_run, dict) and first_run.get("status") == "completed",
            "First fixture project run did not complete.",
        )
        assert_condition(
            isinstance(identical_run, dict)
            and identical_run.get("status") == "completed",
            "Identical fixture project rerun did not complete.",
        )
        assert_condition(
            isinstance(first_run, dict) and first_run.get("items_found", 0) >= 17,
            "Fixture project loaded too few raw items.",
        )
        assert_condition(
            isinstance(first_run, dict) and first_run.get("signals_detected", 0) >= 15,
            "Fixture project detected too few signals.",
        )
        assert_condition(
            isinstance(first_run, dict)
            and first_run.get("opportunities_created", 0) >= 5,
            "Fixture project generated too few opportunities.",
        )
        assert_condition(
            isinstance(first_threads, list) and len(first_threads) >= 5,
            "First fixture run generated too few opportunity threads.",
        )
        assert_condition(
            isinstance(second_threads, list)
            and isinstance(first_threads, list)
            and len(second_threads) == len(first_threads),
            "Identical fixture rerun created a false new opportunity thread.",
        )
        assert_condition(
            isinstance(project_runs, list) and len(project_runs) == 2,
            "Project run history did not contain exactly two fixture runs.",
        )
        if not all(
            isinstance(value, list)
            for value in (first_threads, second_threads, project_runs)
        ):
            raise SmokeError("V1 run/thread responses were not lists.")
        if not isinstance(identical_run, dict) or not isinstance(first_run, dict):
            raise SmokeError("V1 scan responses were not objects.")

        latest_run, original_run = project_runs
        assert_condition(
            latest_run.get("scan_id") == identical_run.get("id")
            and original_run.get("scan_id") == first_run.get("id"),
            "Project run history did not preserve scan linkage.",
        )
        identical_delta = client_json(
            client,
            "GET",
            f"/api/v1/research-projects/{project['id']}/runs/{latest_run['id']}/delta",
        )
        assert_condition(
            isinstance(identical_delta, dict)
            and identical_delta.get("previous_run_id") == original_run.get("id"),
            "Identical project run delta did not link to the first run.",
        )
        assert_identical_run_delta(
            identical_delta,
            observed_items=int(identical_run["items_found"]),
            signal_items=int(identical_run["signals_detected"]),
            opportunity_threads=len(second_threads),
        )

        automatically_matched = [
            thread
            for thread in second_threads
            if isinstance(thread, dict)
            and thread.get("snapshot_count") == 2
            and isinstance(thread.get("current_snapshot"), dict)
            and thread["current_snapshot"].get("match_method") == "exact_evidence"
            and thread["current_snapshot"].get("match_confidence") == 1.0
        ]
        assert_condition(
            len(automatically_matched) == len(second_threads),
            "Identical fixture rerun did not exact-match every opportunity thread.",
        )

        assert_condition(isinstance(stats, dict), "Stats response was not an object.")
        assert_condition(stats.get("total_items", 0) >= 17, "Stats show too few items.")
        assert_condition(
            stats.get("opportunities", 0) >= 5, "Stats show too few opportunities."
        )

        first_thread = max(
            second_threads,
            key=lambda thread: (
                float(thread["current_snapshot"].get("opportunity_score", 0))
                if isinstance(thread, dict)
                and isinstance(thread.get("current_snapshot"), dict)
                else 0.0
            ),
        )
        assert_condition(
            isinstance(first_thread, dict)
            and first_thread.get("id")
            and isinstance(first_thread.get("current_snapshot"), dict),
            "Top opportunity thread is missing its current snapshot.",
        )
        if not isinstance(first_thread, dict) or not isinstance(
            first_thread.get("current_snapshot"), dict
        ):
            raise SmokeError("Top opportunity thread is invalid.")
        first_opportunity = first_thread["current_snapshot"]
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
        credential_marker = "SMOKE-CREDENTIAL-VALUE-EXCLUDE-8D3W"
        baseline_evaluation = client_json(client, "GET", "/api/v1/evaluation")
        human_review_count = max(1, (len(evidence_items) + 1) // 2)
        human_labels: list[dict] = []
        for index, item in enumerate(evidence_items[:human_review_count]):
            assert_condition(
                isinstance(item, dict) and item.get("id"), "Evidence item is invalid."
            )
            label = client_json(
                client,
                "POST",
                "/api/v1/labels",
                {
                    "item_id": item["id"],
                    "label": "true_signal",
                    "user_note": evidence_note if index == 0 else None,
                    "expected_version": 0,
                },
            )
            assert_condition(
                isinstance(label, dict)
                and label.get("actor_type") == "human"
                and label.get("label") == "true_signal"
                and label.get("version") == 1,
                "Human evidence label did not persist with actor provenance.",
            )
            if isinstance(label, dict):
                human_labels.append(label)

        human_evaluation = client_json(client, "GET", "/api/v1/evaluation")
        assert_evaluation_review_progress(baseline_evaluation, human_evaluation)
        thread_before_agent = client_json(
            client,
            "GET",
            f"/api/v1/opportunity-threads/{first_thread['id']}",
        )
        assert_condition(
            isinstance(thread_before_agent, dict),
            "Opportunity thread detail was not an object.",
        )
        if not isinstance(thread_before_agent, dict):
            raise SmokeError("Opportunity thread detail was not an object.")
        readiness_before_agent = thread_before_agent["current_snapshot"][
            "evidence_readiness"
        ]

        agent_process_secret = "first-run-smoke-agent-process-only"
        registered_session = client_json(
            client,
            "POST",
            "/api/v1/agent-sessions",
            {
                "process_instance_id": str(uuid4()),
                "client_name": "TaskSignal first-run proof",
                "client_version": "v1",
                "transport": "stdio",
                "secret_hash": hash_session_secret(agent_process_secret),
                "requested_capabilities": sorted(STANDARD_WRITE_CAPABILITIES),
            },
        )
        assert_condition(
            isinstance(registered_session, dict)
            and registered_session.get("status") == "pending",
            "Agent proof session did not register as pending.",
        )
        if not isinstance(registered_session, dict):
            raise SmokeError("Agent proof session response was not an object.")
        approved_session = client_json(
            client,
            "POST",
            f"/api/v1/agent-sessions/{registered_session['id']}/approve",
            {
                "expected_version": registered_session["version"],
                "use_configured_ai": False,
            },
            {"X-Operator-Scan-Token": os.environ["OPERATOR_SCAN_TOKEN"]},
        )
        assert_condition(
            isinstance(approved_session, dict)
            and approved_session.get("status") == "approved",
            "Agent proof session was not explicitly approved.",
        )

        with SessionLocal() as db:
            agent_label = append_evidence_label(
                db,
                item_id=UUID(str(evidence_item["id"])),
                label=EvidenceReviewLabel.FALSE_POSITIVE,
                user_note=credential_marker,
                actor_type="agent",
                agent_session_id=UUID(str(registered_session["id"])),
                expected_version=1,
            )
            db.commit()
            agent_label_id = str(agent_label.id)

        agent_evaluation = client_json(client, "GET", "/api/v1/evaluation")
        reviewed_item = client_json(
            client,
            "GET",
            f"/api/v1/items/{evidence_item['id']}",
        )
        thread_after_agent = client_json(
            client,
            "GET",
            f"/api/v1/opportunity-threads/{first_thread['id']}",
        )
        assert_condition(
            isinstance(reviewed_item, dict)
            and reviewed_item.get("review_label") == "true_signal"
            and reviewed_item.get("agent_review_label") == "false_positive"
            and reviewed_item.get("agent_session_id") == registered_session["id"],
            "Human and agent evidence labels were not separately visible.",
        )
        assert_condition(
            isinstance(human_evaluation, dict)
            and isinstance(agent_evaluation, dict)
            and {
                key: agent_evaluation.get(key)
                for key in (
                    "reviewed_items",
                    "review_coverage",
                    "label_counts",
                    "precision_on_reviewed_positives",
                )
            }
            == {
                key: human_evaluation.get(key)
                for key in (
                    "reviewed_items",
                    "review_coverage",
                    "label_counts",
                    "precision_on_reviewed_positives",
                )
            },
            "Agent label changed human readiness/precision evaluation.",
        )
        assert_condition(
            isinstance(thread_after_agent, dict)
            and thread_after_agent["current_snapshot"]["evidence_readiness"]
            == readiness_before_agent,
            "Agent label changed human evidence readiness.",
        )

        reviewed_opportunity = client_json(
            client,
            "PATCH",
            f"/api/v1/opportunity-threads/{first_thread['id']}/decision",
            {
                "review_state": "promising",
                "review_note": opportunity_note,
                "expected_version": first_thread["version"],
            },
        )
        assert_condition(
            isinstance(reviewed_opportunity, dict)
            and reviewed_opportunity.get("review_state") == "promising",
            "Opportunity decision did not persist.",
        )
        task_pack = client_json(
            client,
            "GET",
            f"/api/v1/opportunities/{first_opportunity['id']}/task-pack.json",
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
            f"/api/v1/opportunities/{first_opportunity['id']}/evidence.md"
        )
        assert_condition(
            evidence_response.status_code == 200,
            "Evidence Markdown export failed.",
        )
        export_text = json.dumps(task_pack, sort_keys=True) + evidence_response.text
        readiness = assert_decision_export_context(task_pack, evidence_response.text)
        assert_condition(
            opportunity_note not in export_text
            and evidence_note not in export_text
            and credential_marker not in export_text,
            "Local review notes leaked into an export.",
        )

        build_candidate = client_json(
            client,
            "PATCH",
            f"/api/v1/opportunity-threads/{first_thread['id']}/decision",
            {
                "review_state": "build_candidate",
                "review_note": opportunity_note,
                "expected_version": reviewed_opportunity["version"],
            },
        )
        assert_condition(
            isinstance(build_candidate, dict)
            and build_candidate.get("review_state") == "build_candidate"
            and build_candidate["current_snapshot"]["evidence_readiness"]["level"]
            in {"medium", "strong"},
            "Eligible opportunity thread was not promoted to build_candidate.",
        )
        if not isinstance(build_candidate, dict):
            raise SmokeError("Build-candidate response was not an object.")
        packet = client_json(
            client,
            "POST",
            f"/api/v1/opportunity-threads/{first_thread['id']}/build-packets",
            {
                "use_configured_ai": False,
                "expected_version": build_candidate["version"],
            },
        )
        assert_condition(
            isinstance(packet, dict), "Build packet response was not an object."
        )
        if not isinstance(packet, dict):
            raise SmokeError("Build packet response was not an object.")

        fetched_packet = client_json(
            client,
            "GET",
            f"/api/v1/build-packets/{packet['id']}",
        )
        listed_packets = client_json(
            client,
            "GET",
            f"/api/v1/opportunity-threads/{first_thread['id']}/build-packets",
        )
        packet_verification = client_json(
            client,
            "GET",
            f"/api/v1/build-packets/{packet['id']}/verify",
        )
        first_download = client.get(f"/api/v1/build-packets/{packet['id']}/download")
        second_download = client.get(f"/api/v1/build-packets/{packet['id']}/download")
        assert_condition(
            first_download.status_code == 200
            and second_download.status_code == 200
            and first_download.headers.get("content-type") == "application/zip",
            "Build packet download failed.",
        )
        assert_condition(
            first_download.content == second_download.content,
            "Repeated immutable build-packet downloads differed.",
        )
        assert_condition(
            fetched_packet == packet,
            "Immutable build packet changed between create and fetch.",
        )
        assert_condition(
            isinstance(listed_packets, list)
            and len(listed_packets) == 1
            and listed_packets[0].get("artifact_count") == len(BUILD_PACKET_FILES),
            "Build packet list did not expose the immutable 10-file snapshot.",
        )

        selected_item_ids = {
            UUID(str(item["id"]))
            for item in evidence_items
            if isinstance(item, dict) and item.get("id")
        }
        selected_identities = {
            (str(item.get("source")), str(item.get("external_id")))
            for item in evidence_items
            if isinstance(item, dict)
        }
        identity_markers = fixture_raw_identity_markers(
            FIXTURE_DIR,
            selected_identities,
        )
        with SessionLocal() as db:
            normalized_rows = db.scalars(
                select(NormalizedItem).where(NormalizedItem.id.in_(selected_item_ids))
            ).all()
            author_hashes = {
                row.author_hash for row in normalized_rows if row.author_hash
            }
        forbidden_marker_categories = privacy_marker_categories(
            local_notes={opportunity_note, evidence_note, credential_marker},
            raw_identities=identity_markers,
            author_hashes=author_hashes,
            runtime_secrets={
                agent_process_secret,
                os.environ["OPERATOR_SCAN_TOKEN"],
                os.environ["AUTHOR_HASH_SALT"],
            },
        )
        forbidden_markers = set().union(*forbidden_marker_categories.values())
        legacy_export_leaks = sorted(
            marker for marker in forbidden_markers if marker in export_text
        )
        assert_condition(
            not legacy_export_leaks,
            f"Task-pack export leaked {len(legacy_export_leaks)} private marker(s).",
        )
        packet_evidence = inspect_build_packet(
            packet,
            first_download.content,
            packet_verification,
            forbidden_marker_categories=forbidden_marker_categories,
        )

        return {
            "health_status": health["status"],
            "readiness_status": api_readiness["status"],
            "raw_items_loaded": first_run["items_found"],
            "normalized_items_created": first_run["items_saved"],
            "signals_detected": first_run["signals_detected"],
            "clusters_created": first_run["clusters_created"],
            "opportunities_created": first_run["opportunities_created"],
            "total_items": stats["total_items"],
            "stats_opportunities": stats["opportunities"],
            "source_breakdown": stats["source_breakdown"],
            "top_opportunity_id": first_opportunity["id"],
            "top_opportunity": first_opportunity["title"],
            "task_pack_evidence_urls": len(task_pack["evidence_urls"]),
            "task_pack_markdown": task_pack["markdown"],
            "task_pack_required_sections": task_pack_required_sections,
            "decision_review_state": reviewed_opportunity["review_state"],
            "evidence_reviews": len(human_labels),
            "evaluation_reviewed_items_before": baseline_evaluation["reviewed_items"],
            "evaluation_reviewed_items": human_evaluation["reviewed_items"],
            "evaluation_review_coverage_before": baseline_evaluation["review_coverage"],
            "evaluation_review_coverage": human_evaluation["review_coverage"],
            "task_pack_readiness": readiness["level"],
            "project_runs": len(project_runs),
            "identical_run_new_evidence": identical_delta["evidence_changes"]["new"],
            "identical_run_seen_before": identical_delta["evidence_changes"][
                "seen_before"
            ],
            "identical_run_unchanged": identical_delta["evidence_changes"]["unchanged"],
            "threads_after_first_run": len(first_threads),
            "threads_after_second_run": len(second_threads),
            "automatically_matched_threads": len(automatically_matched),
            "false_new_threads": len(second_threads) - len(first_threads),
            "human_labels": len(human_labels),
            "agent_labels": 1,
            "human_label_visible": reviewed_item["review_label"] == "true_signal",
            "agent_label_visible": reviewed_item["agent_review_label"]
            == "false_positive",
            "agent_session_provenance": reviewed_item["agent_session_id"]
            == registered_session["id"]
            and bool(agent_label_id),
            "human_precision_before_agent_label": human_evaluation[
                "precision_on_reviewed_positives"
            ],
            "human_precision_after_agent_label": agent_evaluation[
                "precision_on_reviewed_positives"
            ],
            "readiness_before_agent_label": readiness_before_agent["level"],
            "readiness_after_agent_label": thread_after_agent["current_snapshot"][
                "evidence_readiness"
            ]["level"],
            "build_candidate_state": build_candidate["review_state"],
            "build_packet_generation_mode": packet["generation_mode"],
            "build_packet_artifact_count": packet_evidence["artifact_count"],
            "build_packet_manifested_original_count": packet_evidence[
                "manifested_original_count"
            ],
            "build_packet_archive_byte_count": packet_evidence["archive_bytes"],
            "build_packet_archive_sha256": packet_evidence["archive_sha256"],
            "build_packet_server_verified": packet_verification["valid"],
            "build_packet_repeat_download_identical": first_download.content
            == second_download.content,
            "build_packet_immutable_fetch_identical": fetched_packet == packet,
            "build_packet_private_markers_checked": packet_evidence[
                "private_markers_checked"
            ],
            "build_packet_private_marker_counts": packet_evidence[
                "private_marker_counts"
            ],
            "build_packet_privacy_exports": packet_evidence["privacy_exports"],
            "build_packet_archive_bytes": first_download.content,
            "build_packet_manifest_content": packet_manifest_content(packet),
            "build_packet_verification": packet_verification,
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
            f"{result['evidence_reviews']} evidence "
            f"{'review' if result['evidence_reviews'] == 1 else 'reviews'}, "
            "local notes excluded",
            flush=True,
        )
        print(
            "[OK] Identical project rerun: "
            f"new={result['identical_run_new_evidence']}, "
            f"seen-before={result['identical_run_seen_before']}, "
            f"unchanged={result['identical_run_unchanged']}; "
            f"{result['automatically_matched_threads']} exact thread matches, "
            f"{result['false_new_threads']} false new threads",
            flush=True,
        )
        print(
            "[OK] Actor-aware labels: "
            f"{result['human_labels']} human, {result['agent_labels']} agent; "
            "human precision and readiness unchanged by agent self-label",
            flush=True,
        )
        print(
            "[OK] Immutable build packet: "
            f"{result['build_packet_artifact_count']} files, "
            f"{result['build_packet_archive_byte_count']} archive bytes, "
            f"{result['build_packet_private_markers_checked']} private markers excluded, "
            f"categories={result['build_packet_private_marker_counts']}, "
            "server verified",
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
