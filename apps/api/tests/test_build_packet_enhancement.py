from __future__ import annotations

import json

import pytest

from app.services.build_packets.enhancement import (
    AUTHORITATIVE_BANNER,
    ENHANCEABLE_FILENAMES,
    MAX_ENHANCED_FILE_BYTES,
    InvalidBuildPacketEnhancement,
    build_enhancement_prompt,
    manifest_with_enhancement,
    parse_enhanced_documents,
)


def response_payload() -> dict[str, str]:
    return {name: f"# Enhanced {name}\n\nActionable detail." for name in ENHANCEABLE_FILENAMES}


def test_enhancement_uses_fixed_evidence_free_documents_and_authority_banner() -> None:
    artifacts = {
        name: f"# Root {name}\n\nSafe deterministic content."
        for name in ENHANCEABLE_FILENAMES
    }
    artifacts["evidence.md"] = "PRIVATE-EVIDENCE-SENTINEL"
    artifacts["README.md"] = "Root readme"
    prompt = build_enhancement_prompt(artifacts)
    assert "PRIVATE-EVIDENCE-SENTINEL" not in prompt
    assert set(json.loads(prompt.split("\n\n", 1)[1])) == set(ENHANCEABLE_FILENAMES)

    response = response_payload()
    response["agent-brief.md"] += (
        "\n<img src='https://tracker.example/pixel'> "
        "![remote](https://tracker.example/image.png)"
    )
    enhanced = parse_enhanced_documents(json.dumps(response))
    assert set(enhanced) == {f"enhanced/{name}" for name in ENHANCEABLE_FILENAMES}
    assert all(content.startswith(AUTHORITATIVE_BANNER) for content in enhanced.values())
    assert "tracker.example" not in enhanced["enhanced/agent-brief.md"]
    assert "<img" not in enhanced["enhanced/agent-brief.md"]
    assert "[remote image removed]" in enhanced["enhanced/agent-brief.md"]


@pytest.mark.parametrize(
    "payload",
    [
        {**response_payload(), "../escape.md": "unsafe"},
        {name: content for name, content in response_payload().items() if name != "agent-brief.md"},
        {**response_payload(), "agent-brief.md": ""},
        {**response_payload(), "agent-brief.md": "x" * (MAX_ENHANCED_FILE_BYTES + 1)},
    ],
)
def test_enhancement_rejects_extra_missing_empty_and_oversized_output(
    payload: dict[str, str],
) -> None:
    with pytest.raises(InvalidBuildPacketEnhancement):
        parse_enhanced_documents(json.dumps(payload))


def test_enhancement_manifest_hashes_variants_without_replacing_originals() -> None:
    enhanced = parse_enhanced_documents(json.dumps(response_payload()))
    manifest = manifest_with_enhancement(
        {"generation_mode": "deterministic", "file_count": 10, "enhancement": {}},
        status="generated",
        provider="ollama",
        model="qwen",
        enhanced_artifacts=enhanced,
    )
    assert manifest["generation_mode"] == "configured_ai"
    assert manifest["file_count"] == 16
    assert manifest["enhancement"]["status"] == "generated"
    assert len(manifest["enhancement"]["files"]) == 6
