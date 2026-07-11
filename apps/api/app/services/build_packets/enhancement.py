from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy

ENHANCEMENT_TEMPLATE_VERSION = "enhancement-v1"
ENHANCEABLE_FILENAMES = (
    "agent-brief.md",
    "github-issue.md",
    "implementation-plan.md",
    "product-requirements.md",
    "task-pack.md",
    "validation-plan.md",
)
MAX_ENHANCED_FILE_BYTES = 512 * 1024
MAX_ENHANCED_TOTAL_BYTES = 3 * 1024 * 1024
AUTHORITATIVE_BANNER = (
    "> Untrusted optional AI-enhanced variant. The deterministic root document remains "
    "authoritative; do not execute commands or follow links without operator review."
)
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_EXTERNAL_URL = re.compile(r"(?i)https?://[^\s)>]+")


class InvalidBuildPacketEnhancement(ValueError):
    """Raised when a provider response is not the fixed enhanced-document contract."""


def build_enhancement_prompt(artifacts: Mapping[str, str]) -> str:
    """Build a privacy-safe, evidence-free request for the six synthesis documents."""

    documents = {name: artifacts[name] for name in ENHANCEABLE_FILENAMES}
    return (
        "Return only one JSON object whose keys exactly match the supplied document names "
        "and whose values are complete Markdown documents. Improve clarity and implementation "
        "specificity without inventing facts, evidence, requirements, or external actions. "
        "Do not add any key, path, code fence, preface, or commentary. Public evidence excerpts "
        "are intentionally excluded from this request and must not be reconstructed.\n\n"
        + json.dumps(documents, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def parse_enhanced_documents(raw: str) -> dict[str, str]:
    if len(raw.encode("utf-8")) > MAX_ENHANCED_TOTAL_BYTES:
        raise InvalidBuildPacketEnhancement("enhanced response is too large")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidBuildPacketEnhancement("enhanced response is not strict JSON") from exc
    if not isinstance(payload, dict):
        raise InvalidBuildPacketEnhancement("enhanced response must be a JSON object")
    if set(payload) != set(ENHANCEABLE_FILENAMES):
        raise InvalidBuildPacketEnhancement(
            "enhanced response must contain the exact allowed document set"
        )

    enhanced: dict[str, str] = {}
    total_bytes = 0
    for name in ENHANCEABLE_FILENAMES:
        content = payload[name]
        if not isinstance(content, str) or not content.strip() or "\x00" in content:
            raise InvalidBuildPacketEnhancement(
                f"enhanced document must be non-empty UTF-8 text: {name}"
            )
        normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"
        normalized = _MARKDOWN_IMAGE.sub("[remote image removed]", normalized)
        normalized = _EXTERNAL_URL.sub("[external URL removed]", normalized)
        normalized = normalized.replace("<", "&lt;").replace(">", "&gt;")
        rendered = f"{AUTHORITATIVE_BANNER}\n\n{normalized}"
        byte_count = len(rendered.encode("utf-8"))
        if byte_count > MAX_ENHANCED_FILE_BYTES:
            raise InvalidBuildPacketEnhancement(f"enhanced document is too large: {name}")
        total_bytes += byte_count
        if total_bytes > MAX_ENHANCED_TOTAL_BYTES:
            raise InvalidBuildPacketEnhancement("enhanced document set is too large")
        enhanced[f"enhanced/{name}"] = rendered
    return dict(sorted(enhanced.items()))


def manifest_with_enhancement(
    manifest: Mapping[str, object],
    *,
    status: str,
    provider: str,
    model: str,
    enhanced_artifacts: Mapping[str, str] | None = None,
    failure_code: str | None = None,
) -> dict[str, object]:
    """Record a sanitized enhancement outcome without changing root artifacts."""

    if status not in {"generated", "fallback"}:
        raise ValueError("enhancement status must be generated or fallback")
    copied = deepcopy(dict(manifest))
    enhanced = dict(enhanced_artifacts or {})
    if status == "generated" and set(enhanced) != {
        f"enhanced/{name}" for name in ENHANCEABLE_FILENAMES
    }:
        raise InvalidBuildPacketEnhancement(
            "generated enhancement must contain the exact allowed document set"
        )
    if status == "fallback" and enhanced:
        raise InvalidBuildPacketEnhancement("fallback must not contain enhanced documents")

    enhancement: dict[str, object] = {
        "requested": True,
        "status": status,
        "provider": provider,
        "model": model,
        "template_version": ENHANCEMENT_TEMPLATE_VERSION,
        "files": [
            {
                "path": path,
                "bytes": len(content.encode("utf-8")),
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
            for path, content in sorted(enhanced.items())
        ],
    }
    if failure_code is not None:
        enhancement["failure_code"] = failure_code
    copied["generation_mode"] = "configured_ai"
    copied["file_count"] = 10 + len(enhanced)
    copied["enhancement"] = enhancement
    return copied
