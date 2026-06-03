from __future__ import annotations

import httpx

from app.core.config import settings


class EnhancementUnavailable(RuntimeError):
    """Raised when optional model-backed enhancement is not configured."""


def configured_provider() -> str:
    provider = settings.llm_provider.strip().lower()
    if provider in {"openai", "ollama"}:
        return provider
    return "none"


def parse_openai_text(payload: dict) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n\n".join(parts).strip()


def enhancement_instruction() -> str:
    return (
        "You improve TaskSignal build prompts without inventing evidence. "
        "Keep the Markdown structure, preserve source constraints, acceptance "
        "criteria, and privacy notes, and make the implementation plan more "
        "actionable for a coding agent."
    )


def enhance_prompt(prompt: str) -> tuple[str, str, str]:
    provider = configured_provider()
    if provider == "openai":
        return enhance_prompt_with_openai(prompt)
    if provider == "ollama":
        return enhance_prompt_with_ollama(prompt)
    raise EnhancementUnavailable("Set LLM_PROVIDER=openai or LLM_PROVIDER=ollama first.")


def enhance_prompt_with_openai(prompt: str) -> tuple[str, str, str]:
    if not settings.openai_api_key:
        raise EnhancementUnavailable("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")

    response = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.llm_model,
            "instructions": enhancement_instruction(),
            "input": prompt,
        },
        timeout=60,
    )
    response.raise_for_status()
    enhanced = parse_openai_text(response.json())
    if not enhanced:
        raise EnhancementUnavailable("OpenAI returned no text output.")
    return "openai", settings.llm_model, enhanced


def enhance_prompt_with_ollama(prompt: str) -> tuple[str, str, str]:
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json={
            "model": settings.llm_model,
            "prompt": f"{enhancement_instruction()}\n\n{prompt}",
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    enhanced = str(response.json().get("response", "")).strip()
    if not enhanced:
        raise EnhancementUnavailable("Ollama returned no text output.")
    return "ollama", settings.llm_model, enhanced
