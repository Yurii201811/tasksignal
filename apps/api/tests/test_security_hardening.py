from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.config import Settings, settings
from app.db.session import (
    SQLITE_COMPAT_COLUMNS,
    _validate_sqlite_identifier,
    ensure_sqlite_schema_compatibility,
)
from app.main import CORS_ALLOWED_HEADERS, CORS_ALLOWED_METHODS, create_app


def test_cors_uses_explicit_methods_and_headers(client) -> None:
    assert "*" not in CORS_ALLOWED_METHODS
    assert "*" not in CORS_ALLOWED_HEADERS
    response = client.options(
        "/api/readiness",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Operator-Scan-Token, Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_health_redacts_internal_runtime_outside_local(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "operator_scan_token", "prod-health-secret")

    unauthenticated = client.get("/health")
    assert unauthenticated.status_code == 200
    assert unauthenticated.json() == {"status": "ok"}

    authenticated = client.get("/health", headers={"X-Operator-Scan-Token": "prod-health-secret"})
    assert authenticated.status_code == 200
    body = authenticated.json()
    assert body["status"] == "ok"
    assert "llm_provider" in body
    assert "embedding_model" in body


def test_high_load_endpoints_enforce_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 2)
    app = create_app()
    with TestClient(app) as limited_client:
        first = limited_client.post("/api/search/semantic", json={"query": "rate limit test"})
        second = limited_client.post("/api/search/semantic", json={"query": "rate limit test"})
        third = limited_client.post("/api/search/semantic", json={"query": "rate limit test"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert int(third.headers["Retry-After"]) >= 1


def test_settings_default_rate_limit_enables_outside_local() -> None:
    local_cfg = Settings(environment="local", author_hash_salt="change-me")
    prod_cfg = Settings(environment="production", author_hash_salt="unique-prod-salt-123")

    assert local_cfg.effective_rate_limit_per_minute == 0
    assert prod_cfg.effective_rate_limit_per_minute == 60


def test_sqlite_compat_rejects_unsafe_identifiers(tmp_path: Path, monkeypatch) -> None:
    with pytest.raises(ValueError, match="Unsafe SQLite"):
        _validate_sqlite_identifier("scan_jobs; DROP TABLE scan_jobs", "table")

    db_file = tmp_path / "compat.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    with test_engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE safe_tbl (id INTEGER PRIMARY KEY)")
    monkeypatch.setitem(SQLITE_COMPAT_COLUMNS, "safe_tbl", [("bad;col", "TEXT")])
    with pytest.raises(ValueError, match="Unsafe SQLite column identifier"):
        ensure_sqlite_schema_compatibility(test_engine)
    test_engine.dispose()
