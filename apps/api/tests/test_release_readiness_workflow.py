from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_release_evidence_removes_unuploaded_hidden_build_helpers() -> None:
    workflow = (ROOT / ".github/workflows/release-check.yml").read_text(
        encoding="utf-8"
    )

    remove_helper = workflow.index("rm -f release-artifacts/dist/.gitignore")
    checksum_manifest = workflow.index("find . -type f ! -name SHA256SUMS")

    assert remove_helper < checksum_manifest
    assert "include-hidden-files: true" not in workflow
