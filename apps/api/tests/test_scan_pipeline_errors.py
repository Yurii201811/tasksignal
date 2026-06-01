from __future__ import annotations

import httpx

from app.services.ingestion.connectors import (
    ConnectorError,
    GitHubIssuesConnector,
    connector_failure_message,
    sanitize_error_message,
)
from app.workers.scan_pipeline import process_scan


class SecretLeakingConnector:
    name = "mock"

    def fetch(self, query: str = "", limit: int = 50) -> list:
        raise RuntimeError(
            "Upstream failed Authorization: Bearer abc123 and client_secret=fake-secret-value"
        )


def test_missing_reddit_credentials_produce_actionable_failed_scan(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.config.settings.reddit_client_id",
        "",
    )
    monkeypatch.setattr(
        "app.core.config.settings.reddit_client_secret",
        "",
    )
    monkeypatch.setattr(
        "app.core.config.settings.reddit_user_agent",
        "",
    )

    job = process_scan(db_session, source="reddit", query="automation", limit=5)

    assert job.status == "failed"
    assert job.error_message is not None
    assert "Reddit" in job.error_message
    assert "REDDIT_CLIENT_ID" in job.error_message
    assert ".env" in job.error_message
    assert "fake-secret-value" not in job.error_message


def test_github_rate_limit_error_is_actionable_without_secret_leak(db_session, monkeypatch) -> None:
    request = httpx.Request("GET", "https://api.github.com/search/issues")
    response = httpx.Response(403, request=request, text='{"message":"rate limit"}')
    error = httpx.HTTPStatusError(
        "Client error '403 Forbidden' Authorization: Bearer super-secret-token",
        request=request,
        response=response,
    )

    def raise_rate_limit(self, query: str = "", limit: int = 30):
        raise error

    monkeypatch.setattr(GitHubIssuesConnector, "fetch", raise_rate_limit)

    job = process_scan(db_session, source="github", query="is:issue is:open", limit=5)

    assert job.status == "failed"
    assert job.error_message is not None
    assert "GitHub" in job.error_message
    assert "Issues" in job.error_message or "issues" in job.error_message.lower()
    assert "GITHUB_TOKEN" in job.error_message
    assert "super-secret-token" not in job.error_message
    assert "Bearer abc123" not in job.error_message
    assert "Authorization: Bearer" not in job.error_message


def test_generic_connector_exception_redacts_secrets_in_error_message(db_session) -> None:
    job = process_scan(
        db_session,
        source="mock",
        query="test",
        limit=3,
        connector=SecretLeakingConnector(),
    )

    assert job.status == "failed"
    assert job.error_message is not None
    assert "abc123" not in job.error_message
    assert "fake-secret-value" not in job.error_message
    assert "[redacted secret]" in job.error_message


def test_sanitize_error_message_redacts_common_secret_patterns() -> None:
    raw = "Bearer abc123 client_secret=something token=query-leak"
    sanitized = sanitize_error_message(raw)

    assert "abc123" not in sanitized
    assert "something" not in sanitized
    assert "query-leak" not in sanitized
    assert "[redacted secret]" in sanitized


def test_connector_failure_message_includes_reddit_guidance() -> None:
    message = connector_failure_message(
        "reddit",
        ConnectorError(
            "Reddit credentials are missing. Set REDDIT_CLIENT_ID, "
            "REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT."
        ),
    )

    assert "Reddit" in message
    assert "REDDIT_CLIENT_ID" in message
    assert ".env" in message
    assert "USER_AGENT.." not in message
