from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_pr_validation_workflows_do_not_duplicate_feature_branch_pushes() -> None:
    for relative in (
        ".github/workflows/ci.yml",
        ".github/workflows/postgres-migration-rehearsal.yml",
    ):
        workflow = (ROOT / relative).read_text(encoding="utf-8")

        assert "  push:\n    branches: [\"main\"]\n" in workflow
        assert "  pull_request:\n" in workflow
        assert "  workflow_dispatch:\n" in workflow
