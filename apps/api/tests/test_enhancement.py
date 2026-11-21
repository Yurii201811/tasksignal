from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.generation import enhancement


def test_lm_studio_uses_bounded_chat_completions_and_exact_model(monkeypatch) -> None:
    captured: dict = {}

    def fake_bounded_json(url: str, **kwargs) -> dict:
        captured.update(url=url, **kwargs)
        return {"choices": [{"message": {"content": " Enhanced prompt "}}]}

    monkeypatch.setattr(enhancement.settings, "llm_provider", "lmstudio")
    monkeypatch.setattr(enhancement.settings, "llm_model", "publisher/exact-loaded-model")
    monkeypatch.setattr(enhancement.settings, "lm_studio_base_url", "http://127.0.0.1:1234/v1/")
    monkeypatch.setattr(enhancement, "bounded_provider_json", fake_bounded_json)

    provider, model, text = enhancement.enhance_prompt("Original prompt")

    assert (provider, model, text) == (
        "lmstudio",
        "publisher/exact-loaded-model",
        "Enhanced prompt",
    )
    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert captured["payload"]["model"] == "publisher/exact-loaded-model"
    assert captured["payload"]["messages"][1] == {"role": "user", "content": "Original prompt"}
    assert captured["payload"]["stream"] is False


def test_lm_studio_requires_exact_model_id(monkeypatch) -> None:
    monkeypatch.setattr(enhancement.settings, "llm_model", "  ")

    with pytest.raises(enhancement.EnhancementUnavailable, match="exact model identifier"):
        enhancement.enhance_prompt_with_lm_studio("Original prompt")


def test_lm_studio_rejects_empty_chat_completion(monkeypatch) -> None:
    monkeypatch.setattr(enhancement.settings, "llm_model", "loaded-model")
    monkeypatch.setattr(
        enhancement,
        "bounded_provider_json",
        lambda *args, **kwargs: {"choices": []},
    )

    with pytest.raises(enhancement.EnhancementUnavailable, match="no text output"):
        enhancement.enhance_prompt_with_lm_studio("Original prompt")


@pytest.mark.parametrize("salt", ["", "change-me", "change-me-local"])
def test_non_local_environment_rejects_default_author_hash_salt(salt: str) -> None:
    with pytest.raises(ValueError, match="AUTHOR_HASH_SALT"):
        Settings(_env_file=None, environment="production", author_hash_salt=salt)


def test_non_local_environment_accepts_custom_author_hash_salt() -> None:
    cfg = Settings(
        _env_file=None,
        environment="production",
        author_hash_salt="unique-production-salt-value",
    )
    assert cfg.environment == "production"
    assert cfg.author_hash_salt == "unique-production-salt-value"


def test_local_environment_allows_default_author_hash_salt() -> None:
    cfg = Settings(_env_file=None, environment="local", author_hash_salt="change-me")
    assert cfg.environment == "local"
