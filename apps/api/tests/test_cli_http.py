from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.cli_http import TaskSignalHttpClient

PROJECT_ID = UUID("11111111-1111-4111-8111-111111111111")
RUN_ID = UUID("22222222-2222-4222-8222-222222222222")
THREAD_ID = UUID("33333333-3333-4333-8333-333333333333")
SNAPSHOT_ID = UUID("44444444-4444-4444-8444-444444444444")
ITEM_ID = UUID("55555555-5555-4555-8555-555555555555")
PACKET_ID = UUID("66666666-6666-4666-8666-666666666666")
SESSION_ID = UUID("77777777-7777-4777-8777-777777777777")


def _json_body(request: httpx.Request) -> Any:
    return json.loads(request.content) if request.content else None


def test_client_uses_canonical_api_root_and_environment_token(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[{"id": str(PROJECT_ID)}])

    monkeypatch.setenv("TASKSIGNAL_API_URL", "https://tasksignal.local:9000/")
    monkeypatch.setenv("TASKSIGNAL_API_BASE", "https://legacy-ignored.invalid")
    monkeypatch.setenv("TASKSIGNAL_OPERATOR_TOKEN", "local-operator-secret")
    with TaskSignalHttpClient(transport=httpx.MockTransport(handler)) as client:
        result = client.projects_list()

    assert result == {
        "ok": True,
        "data": [{"id": str(PROJECT_ID)}],
        "error": None,
        "meta": {
            "method": "GET",
            "path": "/research-projects",
            "status": 200,
        },
    }
    assert requests[0].url == httpx.URL("https://tasksignal.local:9000/api/v1/research-projects")
    assert requests[0].headers["X-Operator-Scan-Token"] == "local-operator-secret"


def test_health_uses_the_server_root_and_keeps_error_details_redacted() -> None:
    token = "health-private-token"
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(503, json={"detail": f"token={token}"})

    with TaskSignalHttpClient(
        base_url="https://tasksignal.local:9000/api/v1",
        operator_token=token,
        transport=httpx.MockTransport(handler),
    ) as client:
        healthy = client.health()
        unhealthy = client.health()

    assert [request.url for request in requests] == [
        httpx.URL("https://tasksignal.local:9000/health"),
        httpx.URL("https://tasksignal.local:9000/health"),
    ]
    assert all("X-Operator-Scan-Token" not in request.headers for request in requests)
    assert healthy == {
        "ok": True,
        "data": {"status": "ok"},
        "error": None,
        "meta": {"method": "GET", "path": "/health", "status": 200},
    }
    assert unhealthy["error"] == {
        "code": "http_503",
        "message": "[REDACTED]",
        "status": 503,
    }
    assert token not in json.dumps(unhealthy)


def test_legacy_api_base_is_used_only_when_canonical_url_is_absent(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[])

    monkeypatch.delenv("TASKSIGNAL_API_URL", raising=False)
    monkeypatch.delenv("TASKSIGNAL_OPERATOR_TOKEN", raising=False)
    monkeypatch.setenv("TASKSIGNAL_API_BASE", "https://legacy.local:9443")
    with TaskSignalHttpClient(transport=httpx.MockTransport(handler)) as client:
        client.projects_list()

    assert requests[0].url == httpx.URL("https://legacy.local:9443/api/v1/research-projects")


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://[::1]:8000",
    ],
)
def test_plain_http_is_allowed_for_explicit_loopback_hosts(base_url: str) -> None:
    with TaskSignalHttpClient(
        base_url=base_url,
        operator_token="local-token",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    ) as client:
        assert client.projects_list()["ok"] is True


@pytest.mark.parametrize(
    "base_url",
    [
        "http://tasksignal.local:8000",
        "http://192.168.1.40:8000",
        "http://localhost.example:8000",
    ],
)
def test_plain_http_is_rejected_for_non_loopback_hosts(base_url: str) -> None:
    token = "must-never-cross-plain-http"
    with pytest.raises(ValueError, match="HTTPS") as exc_info:
        TaskSignalHttpClient(base_url=base_url, operator_token=token)

    assert token not in str(exc_info.value)


def test_noun_first_methods_use_only_the_fixed_v1_routes() -> None:
    observed: list[tuple[str, str, dict[str, str], Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(
            (
                request.method,
                request.url.path,
                dict(request.url.params.multi_items()),
                _json_body(request),
            )
        )
        return httpx.Response(200, json={"accepted": True})

    with TaskSignalHttpClient(
        base_url="http://127.0.0.1:8000/api/v1",
        operator_token="operator-token",
        transport=httpx.MockTransport(handler),
    ) as client:
        results = [
            client.projects_list(),
            client.projects_get(PROJECT_ID),
            client.projects_create(
                name="Forum research",
                description="Public pain points",
                source_type="discourse",
                source_id=ITEM_ID,
                query="deployment",
                limit=12,
                cadence="daily",
                schedule_interval_hours=24,
                labels=["indie", "ops"],
                enabled=True,
            ),
            client.projects_update(
                PROJECT_ID,
                expected_version=3,
                description=None,
                enabled=False,
            ),
            client.projects_run(PROJECT_ID),
            client.runs_list(PROJECT_ID),
            client.runs_delta(PROJECT_ID, RUN_ID),
            client.opportunities_list(project_id=PROJECT_ID, review_state="build_candidate"),
            client.opportunities_get(THREAD_ID),
            client.opportunities_search(
                query="slow deployment",
                limit=7,
                project_id=PROJECT_ID,
                source="discourse",
                signal_type="pain",
                review_state="build_candidate",
            ),
            client.opportunities_decision(
                THREAD_ID,
                review_state="build_candidate",
                review_note="Validated manually",
                expected_version=4,
            ),
            client.opportunities_detach(
                THREAD_ID,
                SNAPSHOT_ID,
                expected_version=5,
            ),
            client.evidence_label(
                ITEM_ID,
                label="true_signal",
                user_note="Public evidence confirmed",
                expected_version=2,
            ),
            client.packets_list(THREAD_ID, limit=8, offset=2),
            client.packets_get(PACKET_ID),
            client.packets_create(
                THREAD_ID,
                expected_version=6,
                use_configured_ai=True,
            ),
            client.packets_verify(PACKET_ID),
            client.sessions_list(),
            client.sessions_get(SESSION_ID),
            client.sessions_approve(
                SESSION_ID,
                expected_version=1,
                use_configured_ai=True,
            ),
            client.sessions_revoke(SESSION_ID, expected_version=2),
            client.sessions_actions(SESSION_ID, limit=25, offset=5),
        ]

    assert all(result["ok"] for result in results)
    assert observed == [
        ("GET", "/api/v1/research-projects", {}, None),
        ("GET", f"/api/v1/research-projects/{PROJECT_ID}", {}, None),
        (
            "POST",
            "/api/v1/research-projects",
            {},
            {
                "name": "Forum research",
                "description": "Public pain points",
                "source_type": "discourse",
                "source_id": str(ITEM_ID),
                "query": "deployment",
                "limit": 12,
                "cadence": "daily",
                "schedule_interval_hours": 24,
                "labels": ["indie", "ops"],
                "enabled": True,
            },
        ),
        (
            "PATCH",
            f"/api/v1/research-projects/{PROJECT_ID}",
            {},
            {"expected_version": 3, "description": None, "enabled": False},
        ),
        ("POST", f"/api/v1/research-projects/{PROJECT_ID}/run", {}, None),
        ("GET", f"/api/v1/research-projects/{PROJECT_ID}/runs", {}, None),
        (
            "GET",
            f"/api/v1/research-projects/{PROJECT_ID}/runs/{RUN_ID}/delta",
            {},
            None,
        ),
        (
            "GET",
            "/api/v1/opportunity-threads",
            {"project_id": str(PROJECT_ID), "review_state": "build_candidate"},
            None,
        ),
        ("GET", f"/api/v1/opportunity-threads/{THREAD_ID}", {}, None),
        (
            "POST",
            "/api/v1/search",
            {},
            {
                "query": "slow deployment",
                "limit": 7,
                "project_id": str(PROJECT_ID),
                "source": "discourse",
                "signal_type": "pain",
                "review_state": "build_candidate",
            },
        ),
        (
            "PATCH",
            f"/api/v1/opportunity-threads/{THREAD_ID}/decision",
            {},
            {
                "review_state": "build_candidate",
                "review_note": "Validated manually",
                "expected_version": 4,
            },
        ),
        (
            "POST",
            f"/api/v1/opportunity-threads/{THREAD_ID}/snapshots/{SNAPSHOT_ID}/detach",
            {},
            {"expected_version": 5},
        ),
        (
            "POST",
            "/api/v1/labels",
            {},
            {
                "item_id": str(ITEM_ID),
                "label": "true_signal",
                "user_note": "Public evidence confirmed",
                "expected_version": 2,
            },
        ),
        (
            "GET",
            f"/api/v1/opportunity-threads/{THREAD_ID}/build-packets",
            {"limit": "8", "offset": "2"},
            None,
        ),
        ("GET", f"/api/v1/build-packets/{PACKET_ID}", {}, None),
        (
            "POST",
            f"/api/v1/opportunity-threads/{THREAD_ID}/build-packets",
            {},
            {"use_configured_ai": True, "expected_version": 6},
        ),
        ("GET", f"/api/v1/build-packets/{PACKET_ID}/verify", {}, None),
        ("GET", "/api/v1/agent-sessions", {}, None),
        ("GET", f"/api/v1/agent-sessions/{SESSION_ID}", {}, None),
        (
            "POST",
            f"/api/v1/agent-sessions/{SESSION_ID}/approve",
            {},
            {"expected_version": 1, "use_configured_ai": True},
        ),
        (
            "POST",
            f"/api/v1/agent-sessions/{SESSION_ID}/revoke",
            {},
            {"expected_version": 2},
        ),
        (
            "GET",
            f"/api/v1/agent-sessions/{SESSION_ID}/actions",
            {"limit": "25", "offset": "5"},
            None,
        ),
    ]


def test_project_update_omits_unspecified_fields_but_preserves_explicit_null() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(_json_body(request))
        return httpx.Response(200, json={})

    with TaskSignalHttpClient(transport=httpx.MockTransport(handler)) as client:
        client.projects_update(PROJECT_ID, expected_version=None, source_id=None)

    assert bodies == [{"expected_version": None, "source_id": None}]


def test_http_errors_and_transport_errors_are_stable_and_redacted(monkeypatch) -> None:
    token = "operator-super-secret"

    def forbidden(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"detail": f"Bearer {token}; token=source-private-secret"},
        )

    with TaskSignalHttpClient(
        base_url="https://local.invalid",
        operator_token=token,
        transport=httpx.MockTransport(forbidden),
    ) as client:
        forbidden_result = client.sessions_list()

    serialized = json.dumps(forbidden_result)
    assert forbidden_result["ok"] is False
    assert forbidden_result["error"]["code"] == "http_403"
    assert forbidden_result["error"]["status"] == 403
    assert token not in serialized
    assert "source-private-secret" not in serialized

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            f"request with X-Operator-Scan-Token={token} timed out at {request.url}",
            request=request,
        )

    with TaskSignalHttpClient(
        base_url="https://local.invalid",
        operator_token=token,
        transport=httpx.MockTransport(timeout),
    ) as client:
        timeout_result = client.opportunities_search(query="private customer query")

    assert timeout_result["error"] == {
        "code": "timeout",
        "message": "TaskSignal did not respond before the request timeout.",
        "status": None,
    }
    assert token not in json.dumps(timeout_result)
    assert "private customer query" not in json.dumps(timeout_result)

    monkeypatch.delenv("TASKSIGNAL_OPERATOR_TOKEN", raising=False)


def test_redirects_are_not_followed_with_the_operator_token() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://attacker.invalid/collect"})

    with TaskSignalHttpClient(
        operator_token="must-not-leak",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.projects_list()

    assert len(requests) == 1
    assert result["error"] == {
        "code": "http_302",
        "message": "TaskSignal returned HTTP 302.",
        "status": 302,
    }


def test_packet_download_writes_only_the_explicit_output_and_reports_bytes(tmp_path: Path) -> None:
    archive = b"PK\x03\x04fixture-zip"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v1/build-packets/{PACKET_ID}/download"
        return httpx.Response(
            200,
            content=archive,
            headers={"Content-Type": "application/zip"},
        )

    output = tmp_path / "packet.zip"
    with TaskSignalHttpClient(transport=httpx.MockTransport(handler)) as client:
        result = client.packets_download(PACKET_ID, output_path=output)

    assert result == {
        "ok": True,
        "data": {"path": str(output.resolve()), "bytes": len(archive)},
        "error": None,
        "meta": {
            "method": "GET",
            "path": f"/build-packets/{PACKET_ID}/download",
            "status": 200,
        },
    }
    assert output.read_bytes() == archive
    assert os.stat(output).st_mode & 0o777 == 0o600


def test_packet_download_refuses_existing_or_non_zip_outputs(tmp_path: Path) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, content=b"not a zip", headers={"Content-Type": "text/html"})

    existing = tmp_path / "existing.zip"
    existing.write_bytes(b"keep")
    with TaskSignalHttpClient(transport=httpx.MockTransport(handler)) as client:
        exists_result = client.packets_download(PACKET_ID, output_path=existing)
        invalid_result = client.packets_download(
            PACKET_ID,
            output_path=tmp_path / "invalid.zip",
        )

    assert exists_result["error"]["code"] == "output_exists"
    assert requests == 1
    assert invalid_result["error"] == {
        "code": "invalid_response",
        "message": "TaskSignal returned an invalid build-packet archive.",
        "status": 200,
    }
    assert not (tmp_path / "invalid.zip").exists()
    assert existing.read_bytes() == b"keep"


def test_malformed_identifiers_and_dangling_output_symlinks_are_not_echoed_or_followed(
    tmp_path: Path,
) -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(
            200,
            content=b"PK\x03\x04archive",
            headers={"Content-Type": "application/zip"},
        )

    secret_shaped_id = "token=identifier-secret"
    target = tmp_path / "unexpected-target.zip"
    output = tmp_path / "packet.zip"
    output.symlink_to(target)
    with TaskSignalHttpClient(transport=httpx.MockTransport(handler)) as client:
        get_result = client.projects_get(secret_shaped_id)
        download_result = client.packets_download(PACKET_ID, output_path=output)

    assert requested_paths == ["/api/v1/research-projects/invalid"]
    assert secret_shaped_id not in json.dumps(get_result)
    assert download_result["error"]["code"] == "output_exists"
    assert output.is_symlink()
    assert not target.exists()


def test_client_repr_never_contains_the_operator_token() -> None:
    client = TaskSignalHttpClient(operator_token="repr-private-token")
    try:
        representation = repr(client)
    finally:
        client.close()

    assert "repr-private-token" not in representation
    assert representation == "TaskSignalHttpClient(base_url='http://127.0.0.1:8000/api/v1')"
