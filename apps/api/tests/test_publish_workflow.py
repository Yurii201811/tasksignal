from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_publication_workflow_is_evidence_gated_recoverable_and_least_privilege() -> None:
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")

    assert 'tags: ["v[0-9]*"]' in workflow
    assert "pull_request:" not in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert (
        "DATABASE_URL: sqlite:////tmp/tasksignal-publish-${{ github.run_id }}-${{ github.run_attempt }}.db"
        in workflow
    )
    assert 'AUTO_CREATE_TABLES: "true"' in workflow
    assert "LLM_PROVIDER: none" in workflow
    assert "python3 scripts/release_check.py" in workflow
    assert "--require-clean" in workflow
    assert '--version "$version"' in workflow
    assert "--require-main-ancestry" in workflow
    assert "release-evidence-${{ github.sha }}" in workflow
    assert "RELEASE_EVIDENCE_MANIFEST.json" in workflow
    assert "release_evidence.py verify" in workflow
    assert "make verify" in workflow
    assert "make python-audit" in workflow
    assert "make package-check" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert "id-token: write" in workflow
    assert "pypi-guard" in workflow
    assert "needs.pypi-decision.outputs.publish == 'true'" in workflow
    assert "python-compatibility:" in workflow
    assert "os: [ubuntu-latest, macos-15]" in workflow
    assert 'python-version: ["3.11", "3.12", "3.13", "3.14"]' in workflow
    assert "attest-python:" in workflow
    assert "stage-containers:" in workflow
    assert "promote-containers:" in workflow
    assert (
        "pypi-decision:\n    needs: [validate, python-distribution, stage-containers]" in workflow
    )
    assert "promote-containers:\n    needs: [validate, stage-containers, publish-pypi]" in workflow
    assert "staging-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    assert "sha-${{ github.sha }}" in workflow
    assert "Refusing to move immutable tag" in workflow
    assert "Preflight refused immutable tag" in workflow
    assert 'for source_ref in "${source_refs[@]}"' in workflow
    assert 'test "$existing" = "$source_digest"' in workflow
    assert "platforms: linux/amd64,linux/arm64" in workflow
    assert "subject-digest: ${{ steps.build.outputs.digest }}" in workflow
    assert "org.opencontainers.image.revision=${{ github.sha }}" in workflow
    assert 'if [[ "$IS_PRERELEASE" == "false" ]]' in workflow
    assert 'gh release create "$GITHUB_REF_NAME" --draft' in workflow
    assert 'gh release edit "$GITHUB_REF_NAME" --draft=false' in workflow
    assert "--clobber" not in workflow
    assert "complete_matching_draft" in workflow
    assert "Draft asset does not match candidate" in workflow
    assert 'missing_assets+=("$local_asset")' in workflow
    assert "go run github.com/rhysd/actionlint/cmd/actionlint@" in workflow
