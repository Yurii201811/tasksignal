from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "release_evidence", ROOT / "scripts/release_evidence.py"
)
assert SPEC is not None and SPEC.loader is not None
release_evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_evidence)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_report(root: Path, relative: str, content: str) -> dict[str, object]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": relative, "sha256": _sha256(path)}


def _write_product(root: Path) -> None:
    for relative, content in {
        "apps/api/app/main.py": "app = object()\n",
        "apps/api/pyproject.toml": '[project]\nname="tasksignal"\n',
        "apps/web/src/app/page.tsx": "export default function Page() {}\n",
        "apps/web/package.json": '{"name":"tasksignal-web"}\n',
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _manual_payload(root: Path, version: str, *, builders: int = 0) -> dict[str, object]:
    repository_root = root.parents[1]
    browser = _write_report(root, "reports/browser.md", "desktop and narrow verified\n")
    accessibility = _write_report(
        root,
        "reports/accessibility.md",
        "keyboard, focus, contrast, and reduced motion verified\n",
    )
    builder_rows = []
    for index in range(builders):
        report = _write_report(
            root,
            f"reports/builder-{index + 1}.md",
            f"opaque builder {index + 1} completed fixture to packet\n",
        )
        builder_rows.append(
            {
                "id": f"builder-{index + 1}",
                "completed": True,
                "evidence": report,
            }
        )
    return {
        "schema_version": "tasksignal.manual-release-evidence/v1",
        "version": version,
        "product_digest": release_evidence.product_digest(repository_root),
        "browser": {**browser, "desktop": True, "narrow": True},
        "accessibility": {
            **accessibility,
            "keyboard": True,
            "reduced_motion": True,
        },
        "builders": builder_rows,
    }


def test_alpha_does_not_claim_unrecorded_manual_evidence(tmp_path: Path) -> None:
    _write_product(tmp_path)

    result = release_evidence.validate_manual_evidence(tmp_path, "1.0.0a1")

    assert result == {"required": False, "validated": False, "builders": 0}


def test_product_digest_changes_when_a_public_fixture_changes(tmp_path: Path) -> None:
    _write_product(tmp_path)
    fixture = tmp_path / "data/fixtures/hn_sample.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text('{"items":[]}\n', encoding="utf-8")
    before = release_evidence.product_digest(tmp_path)

    fixture.write_text('{"items":[{"id":"changed"}]}\n', encoding="utf-8")

    assert release_evidence.product_digest(tmp_path) != before


def test_rc_requires_product_bound_browser_and_accessibility_reports(tmp_path: Path) -> None:
    _write_product(tmp_path)
    evidence_root = tmp_path / "release-evidence" / "1.0.0rc1"
    payload = _manual_payload(evidence_root, "1.0.0rc1")
    evidence_root.mkdir(parents=True, exist_ok=True)
    (evidence_root / "manual-gates.json").write_text(json.dumps(payload), encoding="utf-8")

    result = release_evidence.validate_manual_evidence(tmp_path, "1.0.0rc1")

    assert result["required"] is True
    assert result["validated"] is True
    assert result["builders"] == 0


def test_rc_rejects_a_report_from_different_product_content(tmp_path: Path) -> None:
    _write_product(tmp_path)
    evidence_root = tmp_path / "release-evidence" / "1.0.0rc1"
    payload = _manual_payload(evidence_root, "1.0.0rc1")
    evidence_root.mkdir(parents=True, exist_ok=True)
    (evidence_root / "manual-gates.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "apps/web/src/app/page.tsx").write_text("changed\n", encoding="utf-8")

    with pytest.raises(release_evidence.EvidenceError, match="product digest"):
        release_evidence.validate_manual_evidence(tmp_path, "1.0.0rc1")


def test_rc_rejects_report_paths_that_escape_through_a_symlink(tmp_path: Path) -> None:
    _write_product(tmp_path)
    evidence_root = tmp_path / "release-evidence" / "1.0.0rc1"
    evidence_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "browser.md").write_text("outside\n", encoding="utf-8")
    (evidence_root / "reports").symlink_to(outside, target_is_directory=True)
    payload = {
        "schema_version": "tasksignal.manual-release-evidence/v1",
        "version": "1.0.0rc1",
        "product_digest": release_evidence.product_digest(tmp_path),
        "browser": {
            "path": "reports/browser.md",
            "sha256": _sha256(outside / "browser.md"),
            "desktop": True,
            "narrow": True,
        },
        "accessibility": {
            "path": "reports/browser.md",
            "sha256": _sha256(outside / "browser.md"),
            "keyboard": True,
            "reduced_motion": True,
        },
        "builders": [],
    }
    (evidence_root / "manual-gates.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(release_evidence.EvidenceError, match="missing or unsafe"):
        release_evidence.validate_manual_evidence(tmp_path, "1.0.0rc1")


def test_ga_requires_three_distinct_completed_builder_records(tmp_path: Path) -> None:
    _write_product(tmp_path)
    evidence_root = tmp_path / "release-evidence" / "1.0.0"
    payload = _manual_payload(evidence_root, "1.0.0", builders=2)
    evidence_root.mkdir(parents=True, exist_ok=True)
    (evidence_root / "manual-gates.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(release_evidence.EvidenceError, match="three distinct"):
        release_evidence.validate_manual_evidence(tmp_path, "1.0.0")

    payload = _manual_payload(evidence_root, "1.0.0", builders=3)
    (evidence_root / "manual-gates.json").write_text(json.dumps(payload), encoding="utf-8")
    assert release_evidence.validate_manual_evidence(tmp_path, "1.0.0")["builders"] == 3


def test_evidence_manifest_binds_every_input_to_version_commit_and_run(tmp_path: Path) -> None:
    _write_product(tmp_path)
    input_dir = tmp_path / "input"
    (input_dir / "proof").mkdir(parents=True)
    (input_dir / "proof/MANIFEST.json").write_text("{}\n", encoding="utf-8")
    (input_dir / "postgres-migration.json").write_text(
        json.dumps(
            {
                "ok": True,
                "backend": "postgresql",
                "cases": [
                    {"name": "fresh_empty_to_head"},
                    {"name": "copied_v02_to_head"},
                    {"name": "nonempty_unversioned_fails_closed"},
                    {"name": "foreign_revision_fails_closed"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (input_dir / "sqlite-migration.json").write_text(
        json.dumps(
            {
                "ok": True,
                "backend": "sqlite",
                "cases": [
                    {"name": "fresh_to_head"},
                    {"name": "copied_v02_to_head"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (input_dir / "release-check.txt").write_text("passed\n", encoding="utf-8")
    output_dir = tmp_path / "output"

    manifest = release_evidence.finalize_evidence(
        input_dir=input_dir,
        output_dir=output_dir,
        version="1.0.0a1",
        commit_sha="a" * 40,
        run_url="https://github.com/Yurii201811/tasksignal/actions/runs/123",
        product_digest_value=release_evidence.product_digest(tmp_path),
        manual_summary={"required": False, "validated": False, "builders": 0},
        repository_root=tmp_path,
    )

    assert manifest["commit_sha"] == "a" * 40
    assert manifest["version"] == "1.0.0a1"
    assert {entry["path"] for entry in manifest["artifacts"]} == {
        "postgres-migration.json",
        "proof/MANIFEST.json",
        "release-check.txt",
        "sqlite-migration.json",
    }
    release_evidence.verify_evidence(
        output_dir,
        expected_version="1.0.0a1",
        expected_commit="a" * 40,
    )
    (output_dir / "postgres-migration.json").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(release_evidence.EvidenceError, match="hash mismatch"):
        release_evidence.verify_evidence(output_dir)


def test_finalize_rejects_fabricated_manual_summary_and_product_digest(tmp_path: Path) -> None:
    _write_product(tmp_path)
    input_dir = tmp_path / "input"
    (input_dir / "proof").mkdir(parents=True)
    (input_dir / "proof/MANIFEST.json").write_text("{}\n", encoding="utf-8")
    records = {
        "sqlite-migration.json": {
            "ok": True,
            "backend": "sqlite",
            "cases": [{"name": "fresh_to_head"}, {"name": "copied_v02_to_head"}],
        },
        "postgres-migration.json": {
            "ok": True,
            "backend": "postgresql",
            "cases": [
                {"name": "fresh_empty_to_head"},
                {"name": "copied_v02_to_head"},
                {"name": "nonempty_unversioned_fails_closed"},
                {"name": "foreign_revision_fails_closed"},
            ],
        },
    }
    for name, payload in records.items():
        (input_dir / name).write_text(json.dumps(payload), encoding="utf-8")
    (input_dir / "release-check.txt").write_text("passed\n", encoding="utf-8")

    with pytest.raises(release_evidence.EvidenceError, match="product digest"):
        release_evidence.finalize_evidence(
            input_dir=input_dir,
            output_dir=tmp_path / "bad-digest",
            version="1.0.0a1",
            commit_sha="a" * 40,
            run_url="https://github.com/Yurii201811/tasksignal/actions/runs/123",
            product_digest_value="sha256:" + "0" * 64,
            manual_summary={"required": False, "validated": False, "builders": 0},
            repository_root=tmp_path,
        )

    with pytest.raises(release_evidence.EvidenceError, match="manual evidence summary"):
        release_evidence.finalize_evidence(
            input_dir=input_dir,
            output_dir=tmp_path / "bad-summary",
            version="1.0.0a1",
            commit_sha="a" * 40,
            run_url="https://github.com/Yurii201811/tasksignal/actions/runs/123",
            product_digest_value=release_evidence.product_digest(tmp_path),
            manual_summary={"required": False, "validated": True, "builders": 999},
            repository_root=tmp_path,
        )


def test_pypi_guard_allows_missing_release_and_exact_rerun_only(tmp_path: Path) -> None:
    wheel = tmp_path / "tasksignal-1.0.0a1-py3-none-any.whl"
    sdist = tmp_path / "tasksignal-1.0.0a1.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")

    assert release_evidence.pypi_publish_decision([wheel, sdist], None) == "publish"
    exact = {
        "urls": [
            {"filename": path.name, "digests": {"sha256": _sha256(path)}} for path in (wheel, sdist)
        ]
    }
    assert release_evidence.pypi_publish_decision([wheel, sdist], exact) == "skip_exact"
    exact["urls"][0]["digests"]["sha256"] = "0" * 64
    with pytest.raises(release_evidence.EvidenceError, match="does not match"):
        release_evidence.pypi_publish_decision([wheel, sdist], exact)


def test_sbom_must_name_the_released_tasksignal_as_root_component(tmp_path: Path) -> None:
    sbom = tmp_path / "tasksignal.cdx.json"
    sbom.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "metadata": {
                    "component": {
                        "type": "library",
                        "name": "tasksignal",
                        "version": "1.0.0a1",
                    }
                },
                "components": [],
                "dependencies": [],
            }
        ),
        encoding="utf-8",
    )

    release_evidence.validate_sbom(sbom, "1.0.0a1")
    payload = json.loads(sbom.read_text(encoding="utf-8"))
    payload["metadata"]["component"]["version"] = "0.2.0"
    sbom.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(release_evidence.EvidenceError, match="root component"):
        release_evidence.validate_sbom(sbom, "1.0.0a1")


def test_sbom_canonicalization_removes_run_specific_timestamp_and_uuid(tmp_path: Path) -> None:
    outputs = []
    for index in range(2):
        sbom = tmp_path / f"tasksignal-{index}.cdx.json"
        sbom.write_text(
            json.dumps(
                {
                    "bomFormat": "CycloneDX",
                    "specVersion": "1.5",
                    "version": 1,
                    "serialNumber": f"urn:uuid:00000000-0000-0000-0000-00000000000{index}",
                    "metadata": {
                        "timestamp": f"2026-07-11T12:00:0{index}Z",
                        "component": {"name": "tasksignal", "version": "1.0.0a1"},
                    },
                    "components": [],
                    "dependencies": [],
                }
            ),
            encoding="utf-8",
        )
        release_evidence.canonicalize_sbom(sbom, "1.0.0a1", 1_700_000_000)
        outputs.append(sbom.read_bytes())

    assert outputs[0] == outputs[1]


def test_workflow_policy_requires_explicit_permissions_and_full_action_shas(
    tmp_path: Path,
) -> None:
    workflow = tmp_path / "publish.yml"
    workflow.write_text(
        "permissions:\n  contents: read\nsteps:\n"
        "  - uses: actions/checkout@" + "a" * 40 + " # v6\n",
        encoding="utf-8",
    )
    assert release_evidence.check_workflow_policy(workflow) == []

    workflow.write_text("steps:\n  - uses: actions/checkout@v6\n", encoding="utf-8")
    failures = release_evidence.check_workflow_policy(workflow)
    assert any("top-level permissions" in failure for failure in failures)
    assert any("full commit SHA" in failure for failure in failures)
