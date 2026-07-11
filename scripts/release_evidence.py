#!/usr/bin/env python3
"""Fail-closed release evidence, publication recovery, and workflow policy helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "RELEASE_EVIDENCE_MANIFEST.json"
MANIFEST_SCHEMA = "tasksignal.release-evidence/v1"
MANUAL_SCHEMA = "tasksignal.manual-release-evidence/v1"
CANONICAL_RELEASE = re.compile(
    r"^(?P<base>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))"
    r"(?:(?P<phase>a|b|rc)(?P<number>[1-9]\d*))?$"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
RUN_URL = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/actions/runs/\d+/?$")
ACTION_USES = re.compile(r"^\s*-\s+uses:\s*([^\s#]+)", re.MULTILINE)
FULL_ACTION_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")

PRODUCT_INPUTS = (
    "apps/api/app",
    "apps/api/Dockerfile",
    "apps/api/alembic.ini",
    "apps/api/pyproject.toml",
    "apps/api/uv.lock",
    "apps/web/src",
    "apps/web/Dockerfile",
    "apps/web/package.json",
    "apps/web/package-lock.json",
    "data/fixtures",
    "scripts",
    "skills/tasksignal-opportunity-builder",
)


class EvidenceError(RuntimeError):
    """A release evidence or recovery invariant was not satisfied."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_version(value: str) -> re.Match[str]:
    match = CANONICAL_RELEASE.fullmatch(value)
    if match is None:
        raise EvidenceError(f"Unsupported noncanonical release version: {value}")
    return match


def _phase(value: str) -> str:
    match = _canonical_version(value)
    return {None: "stable", "a": "alpha", "b": "beta", "rc": "rc"}[match.group("phase")]


def _iter_product_files(root: Path) -> list[Path]:
    files: set[Path] = set()
    for relative in PRODUCT_INPUTS:
        candidate = root / relative
        if candidate.is_file():
            files.add(candidate)
        elif candidate.is_dir():
            for path in candidate.rglob("*"):
                if not path.is_file():
                    continue
                relative_parts = path.relative_to(root).parts
                if any(
                    part
                    in {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
                    for part in relative_parts
                ) or path.suffix in {".pyc", ".pyo"}:
                    continue
                files.add(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def product_digest(root: Path = ROOT) -> str:
    """Hash release-relevant product content without self-referential reports."""

    root = root.resolve()
    digest = hashlib.sha256()
    files = _iter_product_files(root)
    if not files:
        raise EvidenceError("No release-relevant product files were found.")
    for path in files:
        if path.is_symlink():
            raise EvidenceError(f"Product input must not be a symlink: {path}")
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return f"sha256:{digest.hexdigest()}"


def _safe_report(root: Path, value: object, *, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} evidence must be an object.")
    relative_value = value.get("path")
    expected_hash = value.get("sha256")
    if not isinstance(relative_value, str) or not relative_value:
        raise EvidenceError(f"{label} evidence path is missing.")
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise EvidenceError(
            f"{label} evidence path must remain inside its candidate directory."
        )
    path = root / relative
    resolved_root = root.resolve()
    try:
        resolved_path = path.resolve(strict=True)
    except OSError as exc:
        raise EvidenceError(
            f"{label} evidence file is missing or unsafe: {relative_value}"
        ) from exc
    parent_is_symlink = False
    current_parent = root
    for part in relative.parts[:-1]:
        current_parent /= part
        if current_parent.is_symlink():
            parent_is_symlink = True
            break
    if (
        path.is_symlink()
        or not resolved_path.is_relative_to(resolved_root)
        or parent_is_symlink
        or not path.is_file()
    ):
        raise EvidenceError(
            f"{label} evidence file is missing or unsafe: {relative_value}"
        )
    if not isinstance(expected_hash, str) or not SHA256.fullmatch(expected_hash):
        raise EvidenceError(f"{label} evidence SHA-256 is invalid.")
    actual_hash = _sha256_file(path)
    if actual_hash != expected_hash:
        raise EvidenceError(f"{label} evidence hash mismatch.")
    return {"path": relative.as_posix(), "sha256": actual_hash}


def validate_manual_evidence(root: Path, version: str) -> dict[str, object]:
    """Require product-bound Browser/a11y evidence for RC/GA and builders for GA."""

    phase = _phase(version)
    if phase not in {"rc", "stable"}:
        return {"required": False, "validated": False, "builders": 0}

    evidence_root = root / "release-evidence" / version
    manifest_path = evidence_root / "manual-gates.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise EvidenceError(f"RC/GA manual evidence is required: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(
            "RC/GA manual evidence is unreadable or malformed."
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != MANUAL_SCHEMA:
        raise EvidenceError("RC/GA manual evidence has an unsupported schema.")
    if payload.get("version") != version:
        raise EvidenceError("RC/GA manual evidence version does not match the release.")
    expected_product_digest = product_digest(root)
    if payload.get("product_digest") != expected_product_digest:
        raise EvidenceError(
            "RC/GA manual evidence product digest does not match this candidate."
        )

    browser = payload.get("browser")
    if not isinstance(browser, dict) or not all(
        browser.get(name) is True for name in ("desktop", "narrow")
    ):
        raise EvidenceError(
            "RC/GA Browser evidence must cover desktop and narrow flows."
        )
    browser_report = _safe_report(evidence_root, browser, label="Browser")

    accessibility = payload.get("accessibility")
    if not isinstance(accessibility, dict) or not all(
        accessibility.get(name) is True for name in ("keyboard", "reduced_motion")
    ):
        raise EvidenceError(
            "RC/GA accessibility evidence must cover keyboard and reduced-motion behavior."
        )
    accessibility_report = _safe_report(
        evidence_root, accessibility, label="Accessibility"
    )

    builders_value = payload.get("builders", [])
    if not isinstance(builders_value, list):
        raise EvidenceError("Builder evidence must be a list.")
    builder_ids: set[str] = set()
    builder_reports: list[dict[str, str]] = []
    for index, row in enumerate(builders_value):
        if not isinstance(row, dict) or row.get("completed") is not True:
            raise EvidenceError(f"Builder evidence row {index + 1} is incomplete.")
        builder_id = row.get("id")
        if not isinstance(builder_id, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9_-]{2,63}", builder_id
        ):
            raise EvidenceError(
                f"Builder evidence row {index + 1} has an invalid opaque ID."
            )
        if builder_id in builder_ids:
            raise EvidenceError("Builder evidence IDs must be distinct.")
        builder_ids.add(builder_id)
        builder_reports.append(
            _safe_report(
                evidence_root, row.get("evidence"), label=f"Builder {index + 1}"
            )
        )
    if phase == "stable" and len(builder_ids) < 3:
        raise EvidenceError(
            "GA requires three distinct completed builder evidence records."
        )

    return {
        "required": True,
        "validated": True,
        "builders": len(builder_ids),
        "product_digest": expected_product_digest,
        "browser": browser_report,
        "accessibility": accessibility_report,
        "builder_reports": builder_reports,
        "source": f"release-evidence/{version}/manual-gates.json",
    }


def copy_manual_evidence(
    root: Path, version: str, destination: Path
) -> dict[str, object]:
    summary = validate_manual_evidence(root, version)
    if summary["required"] is not True:
        return summary
    source = root / "release-evidence" / version
    if any(path.is_symlink() for path in source.rglob("*")):
        raise EvidenceError("Manual evidence must not contain symlinks.")
    target = destination / "manual"
    if target.exists():
        raise EvidenceError(f"Manual evidence destination already exists: {target}")
    shutil.copytree(source, target, symlinks=False)
    return summary


def _validated_migration_record(
    path: Path,
    *,
    backend: str,
    required_cases: set[str],
    label: str,
) -> None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(
            f"{label} migration record is unreadable or malformed."
        ) from exc
    if (
        not isinstance(value, dict)
        or value.get("ok") is not True
        or value.get("backend") != backend
    ):
        raise EvidenceError(f"{label} migration record did not pass.")
    cases = value.get("cases")
    if not isinstance(cases, list) or any(not isinstance(row, dict) for row in cases):
        raise EvidenceError(f"{label} migration record is missing required cases.")
    case_names = {row.get("name") for row in cases}
    if not required_cases <= case_names:
        raise EvidenceError(f"{label} migration record is missing required cases.")


def _artifact_entries(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        if not path.is_file() or path.name == MANIFEST_NAME:
            continue
        if path.is_symlink():
            raise EvidenceError(f"Release evidence must not contain symlinks: {path}")
        content = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": len(content),
                "sha256": _sha256_bytes(content),
            }
        )
    return entries


def finalize_evidence(
    *,
    input_dir: Path,
    output_dir: Path,
    version: str,
    commit_sha: str,
    run_url: str,
    product_digest_value: str,
    manual_summary: dict[str, object],
    repository_root: Path = ROOT,
) -> dict[str, object]:
    _canonical_version(version)
    if not COMMIT_SHA.fullmatch(commit_sha):
        raise EvidenceError("Release evidence requires a full lowercase commit SHA.")
    if not RUN_URL.fullmatch(run_url):
        raise EvidenceError(
            "Release evidence requires an exact GitHub Actions run URL."
        )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", product_digest_value):
        raise EvidenceError("Release evidence product digest is invalid.")
    actual_product_digest = product_digest(repository_root)
    if product_digest_value != actual_product_digest:
        raise EvidenceError(
            "Release evidence product digest does not match this candidate."
        )
    actual_manual_summary = validate_manual_evidence(repository_root, version)
    if manual_summary != actual_manual_summary:
        raise EvidenceError(
            "Release evidence manual evidence summary is not authoritative."
        )
    required = (
        input_dir / "release-check.txt",
        input_dir / "proof" / "MANIFEST.json",
        input_dir / "sqlite-migration.json",
        input_dir / "postgres-migration.json",
    )
    missing = [path for path in required if not path.is_file() or path.is_symlink()]
    if missing:
        raise EvidenceError(
            "Release evidence inputs are missing: " + ", ".join(map(str, missing))
        )
    if any(path.is_symlink() for path in input_dir.rglob("*")):
        raise EvidenceError("Release evidence inputs must not contain symlinks.")
    _validated_migration_record(
        input_dir / "sqlite-migration.json",
        backend="sqlite",
        required_cases={"fresh_to_head", "copied_v02_to_head"},
        label="SQLite",
    )
    _validated_migration_record(
        input_dir / "postgres-migration.json",
        backend="postgresql",
        required_cases={
            "fresh_empty_to_head",
            "copied_v02_to_head",
            "nonempty_unversioned_fails_closed",
            "foreign_revision_fails_closed",
        },
        label="PostgreSQL",
    )
    if output_dir.exists():
        raise EvidenceError(f"Release evidence output already exists: {output_dir}")
    shutil.copytree(input_dir, output_dir, symlinks=False)
    artifacts = _artifact_entries(output_dir)
    manifest: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "version": version,
        "phase": _phase(version),
        "commit_sha": commit_sha,
        "run_url": run_url,
        "product_digest": product_digest_value,
        "manual_evidence": manual_summary,
        "artifacts": artifacts,
    }
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_evidence(output_dir, expected_version=version, expected_commit=commit_sha)
    return manifest


def verify_evidence(
    directory: Path,
    *,
    expected_version: str | None = None,
    expected_commit: str | None = None,
) -> dict[str, object]:
    manifest_path = directory / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(
            "Release evidence manifest is missing or malformed."
        ) from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != MANIFEST_SCHEMA
    ):
        raise EvidenceError("Release evidence manifest schema is unsupported.")
    if expected_version is not None and manifest.get("version") != expected_version:
        raise EvidenceError("Release evidence version mismatch.")
    if expected_commit is not None and manifest.get("commit_sha") != expected_commit:
        raise EvidenceError("Release evidence commit mismatch.")
    entries = manifest.get("artifacts")
    if not isinstance(entries, list):
        raise EvidenceError("Release evidence artifact inventory is invalid.")
    expected_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise EvidenceError("Release evidence artifact entry is invalid.")
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise EvidenceError("Release evidence artifact path is unsafe.")
        path = directory / relative
        if path.is_symlink() or not path.is_file():
            raise EvidenceError(f"Release evidence artifact is missing: {relative}")
        expected_paths.add(relative.as_posix())
        if _sha256_file(path) != entry.get("sha256"):
            raise EvidenceError(f"Release evidence hash mismatch: {relative}")
        if path.stat().st_size != entry.get("bytes"):
            raise EvidenceError(f"Release evidence byte count mismatch: {relative}")
    actual_paths = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != MANIFEST_NAME
    }
    if actual_paths != expected_paths:
        raise EvidenceError(
            "Release evidence contains an unexpected or unmanifested file."
        )
    return manifest


def pypi_publish_decision(
    distributions: Iterable[Path], published_payload: dict[str, Any] | None
) -> str:
    local = {path.name: _sha256_file(path) for path in distributions}
    if not local:
        raise EvidenceError("No Python distributions were supplied to the PyPI guard.")
    if published_payload is None:
        return "publish"
    urls = published_payload.get("urls")
    if not isinstance(urls, list):
        raise EvidenceError("PyPI returned a malformed release record.")
    published: dict[str, str] = {}
    for row in urls:
        if not isinstance(row, dict) or not isinstance(row.get("filename"), str):
            raise EvidenceError("PyPI returned a malformed distribution record.")
        digests = row.get("digests")
        if not isinstance(digests, dict) or not isinstance(digests.get("sha256"), str):
            raise EvidenceError("PyPI omitted a distribution SHA-256 digest.")
        published[row["filename"]] = digests["sha256"]
    if published != local:
        raise EvidenceError(
            "The existing PyPI release does not match the exact local filenames and hashes."
        )
    return "skip_exact"


def fetch_pypi_release(project: str, version: str) -> dict[str, Any] | None:
    _canonical_version(version)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", project):
        raise EvidenceError("PyPI project name is unsafe.")
    url = f"https://pypi.org/pypi/{project}/{version}/json"
    request = urllib.request.Request(
        url, headers={"User-Agent": "tasksignal-release-guard/1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            value = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise EvidenceError(
            f"PyPI release lookup failed with HTTP {exc.code}."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("PyPI release lookup failed closed.") from exc
    if not isinstance(value, dict):
        raise EvidenceError("PyPI returned a malformed release response.")
    return value


def validate_sbom(path: Path, version: str) -> None:
    _canonical_version(version)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("CycloneDX SBOM is missing or malformed.") from exc
    metadata = payload.get("metadata") if isinstance(payload, dict) else None
    component = metadata.get("component") if isinstance(metadata, dict) else None
    if (
        payload.get("bomFormat") != "CycloneDX"
        or payload.get("specVersion") != "1.5"
        or not isinstance(component, dict)
        or component.get("name") != "tasksignal"
        or component.get("version") != version
    ):
        raise EvidenceError(
            "CycloneDX SBOM root component does not match TaskSignal release."
        )
    if not isinstance(payload.get("components"), list) or not isinstance(
        payload.get("dependencies"), list
    ):
        raise EvidenceError("CycloneDX SBOM dependency inventory is malformed.")


def canonicalize_sbom(path: Path, version: str, source_date_epoch: int) -> None:
    """Replace run-specific CycloneDX fields with source-derived stable values."""

    validate_sbom(path, version)
    if source_date_epoch < 0:
        raise EvidenceError("SOURCE_DATE_EPOCH must be nonnegative.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["serialNumber"] = "urn:uuid:" + str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"https://tasksignal.dev/sbom/{version}")
    )
    payload["metadata"]["timestamp"] = (
        datetime.fromtimestamp(source_date_epoch, tz=UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    validate_sbom(path, version)


def check_workflow_policy(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    failures: list[str] = []
    if not re.search(r"^permissions:\s*\n(?:^[ \t]+[^\n]+\n?)+", text, re.MULTILINE):
        failures.append("Workflow must declare top-level permissions explicitly.")
    for uses in ACTION_USES.findall(text):
        if uses.startswith("./") or uses.startswith("docker://"):
            continue
        if not FULL_ACTION_PIN.fullmatch(uses):
            failures.append(f"Action must be pinned to a full commit SHA: {uses}")
    return failures


def run_sqlite_rehearsal(output: Path) -> dict[str, object]:
    """Exercise fresh and copied-v0.2 packaged migrations and preserve the record."""

    api_dir = ROOT / "apps" / "api"
    sys.path.insert(0, str(api_dir))
    from alembic import command  # type: ignore[import-not-found]
    from app.packaged_runtime import (  # type: ignore[import-not-found]
        inspect_schema,
        migrate_database,
        packaged_alembic_config,
    )

    cases: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tasksignal-sqlite-release-") as temporary:
        root = Path(temporary)
        fresh_url = f"sqlite:///{root / 'fresh.db'}"
        fresh = migrate_database(fresh_url)
        if fresh.status.state != "current" or fresh.backup_path is not None:
            raise EvidenceError("Fresh SQLite rehearsal did not reach head safely.")
        cases.append({"name": "fresh_to_head", "state": "current", "backup": False})

        copied_url = f"sqlite:///{root / 'copied-v02.db'}"
        command.upgrade(packaged_alembic_config(copied_url), "0006_decision_workbench")
        copied = migrate_database(copied_url)
        if copied.status.state != "current" or copied.backup_path is None:
            raise EvidenceError(
                "Copied-v0.2 SQLite rehearsal did not back up and reach head."
            )
        backup_status = inspect_schema(f"sqlite:///{copied.backup_path}")
        if backup_status.current_revision != "0006_decision_workbench":
            raise EvidenceError(
                "Copied-v0.2 SQLite backup did not preserve its revision."
            )
        cases.append(
            {
                "name": "copied_v02_to_head",
                "state": "current",
                "backup": True,
                "backup_revision": backup_status.current_revision,
            }
        )
    payload: dict[str, object] = {"ok": True, "backend": "sqlite", "cases": cases}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _write_github_output(path: Path | None, values: dict[str, str]) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise EvidenceError(f"Unsafe multiline GitHub output: {key}")
            handle.write(f"{key}={value}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    digest = commands.add_parser("product-digest")
    digest.add_argument("--root", type=Path, default=ROOT)

    manual = commands.add_parser("validate-manual")
    manual.add_argument("--root", type=Path, default=ROOT)
    manual.add_argument("--version", required=True)
    manual.add_argument("--copy-to", type=Path)
    manual.add_argument("--summary-output", type=Path)

    sqlite = commands.add_parser("sqlite-rehearsal")
    sqlite.add_argument("--output", type=Path, required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--input-dir", type=Path, required=True)
    finalize.add_argument("--output-dir", type=Path, required=True)
    finalize.add_argument("--version", required=True)
    finalize.add_argument("--commit", required=True)
    finalize.add_argument("--run-url", required=True)
    finalize.add_argument("--product-digest", required=True)
    finalize.add_argument("--manual-summary", type=Path, required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--directory", type=Path, required=True)
    verify.add_argument("--version")
    verify.add_argument("--commit")

    pypi = commands.add_parser("pypi-guard")
    pypi.add_argument("--project", default="tasksignal")
    pypi.add_argument("--version", required=True)
    pypi.add_argument("--packages-dir", type=Path, required=True)
    pypi.add_argument("--github-output", type=Path)

    sbom = commands.add_parser("validate-sbom")
    sbom.add_argument("--sbom", type=Path, required=True)
    sbom.add_argument("--version", required=True)
    sbom.add_argument("--canonicalize", action="store_true")
    sbom.add_argument("--source-date-epoch", type=int)

    policy = commands.add_parser("workflow-policy")
    policy.add_argument("--workflow", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "product-digest":
            print(product_digest(args.root))
        elif args.command == "validate-manual":
            summary = (
                copy_manual_evidence(args.root, args.version, args.copy_to)
                if args.copy_to is not None
                else validate_manual_evidence(args.root, args.version)
            )
            rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
            if args.summary_output is not None:
                args.summary_output.parent.mkdir(parents=True, exist_ok=True)
                args.summary_output.write_text(rendered, encoding="utf-8")
            print(rendered, end="")
        elif args.command == "sqlite-rehearsal":
            print(json.dumps(run_sqlite_rehearsal(args.output), sort_keys=True))
        elif args.command == "finalize":
            manual_summary = json.loads(args.manual_summary.read_text(encoding="utf-8"))
            manifest = finalize_evidence(
                input_dir=args.input_dir,
                output_dir=args.output_dir,
                version=args.version,
                commit_sha=args.commit,
                run_url=args.run_url,
                product_digest_value=args.product_digest,
                manual_summary=manual_summary,
                repository_root=ROOT,
            )
            print(json.dumps(manifest, sort_keys=True))
        elif args.command == "verify":
            print(
                json.dumps(
                    verify_evidence(
                        args.directory,
                        expected_version=args.version,
                        expected_commit=args.commit,
                    ),
                    sort_keys=True,
                )
            )
        elif args.command == "pypi-guard":
            distributions = sorted(
                path
                for path in args.packages_dir.iterdir()
                if path.is_file() and path.suffix in {".whl", ".gz"}
            )
            decision = pypi_publish_decision(
                distributions, fetch_pypi_release(args.project, args.version)
            )
            _write_github_output(
                args.github_output,
                {
                    "publish": "true" if decision == "publish" else "false",
                    "decision": decision,
                },
            )
            print(json.dumps({"ok": True, "decision": decision}, sort_keys=True))
        elif args.command == "validate-sbom":
            if args.canonicalize:
                if args.source_date_epoch is None:
                    raise EvidenceError("--canonicalize requires --source-date-epoch.")
                canonicalize_sbom(args.sbom, args.version, args.source_date_epoch)
            validate_sbom(args.sbom, args.version)
            print(json.dumps({"ok": True}, sort_keys=True))
        elif args.command == "workflow-policy":
            failures = check_workflow_policy(args.workflow)
            if failures:
                raise EvidenceError(" ".join(failures))
            print(json.dumps({"ok": True}, sort_keys=True))
        else:  # pragma: no cover - argparse constrains the command.
            raise EvidenceError("Unknown release evidence command.")
    except (EvidenceError, OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
