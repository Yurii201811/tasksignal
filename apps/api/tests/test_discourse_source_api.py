from __future__ import annotations

from app.api import routes


def enable_operator_token(monkeypatch) -> dict[str, str]:
    monkeypatch.setattr(routes.settings, "operator_scan_token", "source-admin-token")
    return {"X-Operator-Scan-Token": "source-admin-token"}


def create_discourse_source(client, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/v1/sources",
        headers=headers,
        json={
            "name": "Builder Forum",
            "type": "discourse",
            "config_json": {},
            "enabled": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def authorize_source(
    client,
    source_id: str,
    headers: dict[str, str],
    origin: str = "https://forum.example",
) -> dict:
    response = client.put(
        f"/api/v1/sources/{source_id}/authorization",
        headers=headers,
        json={"origin": origin, "terms_confirmed": True},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_discourse_authorization_requires_operator_and_explicit_terms(
    client,
    monkeypatch,
) -> None:
    headers = enable_operator_token(monkeypatch)
    source = create_discourse_source(client, headers)
    endpoint = f"/api/v1/sources/{source['id']}/authorization"

    missing_operator = client.put(
        endpoint,
        json={"origin": "https://forum.example", "terms_confirmed": True},
    )
    missing_terms = client.put(
        endpoint,
        headers=headers,
        json={"origin": "https://forum.example", "terms_confirmed": False},
    )
    insecure = client.put(
        endpoint,
        headers=headers,
        json={"origin": "http://forum.example", "terms_confirmed": True},
    )
    ip_literal = client.put(
        endpoint,
        headers=headers,
        json={"origin": "https://127.0.0.1", "terms_confirmed": True},
    )

    assert missing_operator.status_code == 403
    assert missing_terms.status_code == 422
    assert insecure.status_code == 422
    assert ip_literal.status_code == 422

    authorization = authorize_source(client, source["id"], headers)
    assert authorization["source_id"] == source["id"]
    assert authorization["source_type"] == "discourse"
    assert authorization["origin"] == "https://forum.example"
    assert authorization["host"] == "forum.example"
    assert authorization["port"] == 443
    assert authorization["authorized"] is True
    assert authorization["authorized_at"] is not None
    assert authorization["terms_confirmed_at"] is not None

    readable = client.get(endpoint)
    assert readable.status_code == 200
    assert readable.json() == authorization

    changed_origin = client.put(
        endpoint,
        headers=headers,
        json={"origin": "https://other.example", "terms_confirmed": True},
    )
    assert changed_origin.status_code == 409


def test_discourse_authorization_is_type_scoped_and_revocable(client, monkeypatch) -> None:
    headers = enable_operator_token(monkeypatch)
    fixed_source = client.post(
        "/api/v1/sources",
        headers=headers,
        json={
            "name": "HN",
            "type": "hackernews",
            "config_json": {},
            "enabled": True,
        },
    ).json()
    wrong_type = client.put(
        f"/api/v1/sources/{fixed_source['id']}/authorization",
        headers=headers,
        json={"origin": "https://forum.example", "terms_confirmed": True},
    )
    assert wrong_type.status_code == 409

    source = create_discourse_source(client, headers)
    authorize_source(client, source["id"], headers)
    revoked = client.delete(
        f"/api/v1/sources/{source['id']}/authorization",
        headers=headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["authorized"] is False
    assert revoked.json()["authorized_at"] is None
    assert revoked.json()["terms_confirmed_at"] is None

    runtime = client.get(f"/api/v1/sources/{source['id']}/runtime-state")
    assert runtime.status_code == 200
    assert runtime.json()["source_id"] == source["id"]
    assert runtime.json()["readiness"] == "terms_required"


def test_discourse_project_requires_matching_authorized_source(client, monkeypatch) -> None:
    headers = enable_operator_token(monkeypatch)
    discourse = create_discourse_source(client, headers)

    missing_source = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Missing forum",
            "source_type": "discourse",
            "query": "manual workflow",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    unauthorized = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Unauthorized forum",
            "source_type": "discourse",
            "source_id": discourse["id"],
            "query": "manual workflow",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    assert missing_source.status_code == 422
    assert unauthorized.status_code == 409

    authorization = authorize_source(client, discourse["id"], headers)
    created = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Authorized forum",
            "source_type": "discourse",
            "source_id": discourse["id"],
            "query": "manual workflow",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["source_id"] == discourse["id"]

    referenced_delete = client.delete(
        f"/api/v1/sources/{discourse['id']}",
        headers=headers,
    )
    assert referenced_delete.status_code == 409
    assert client.get(
        f"/api/v1/sources/{discourse['id']}/authorization"
    ).status_code == 200

    run = client.get(
        f"/api/v1/research-projects/{created.json()['id']}/runs"
    )
    assert run.status_code == 200
    assert run.json() == []
    assert authorization["origin"] == "https://forum.example"


def test_fixed_connector_projects_reject_mismatched_source_ids(client, monkeypatch) -> None:
    headers = enable_operator_token(monkeypatch)
    fixed = client.post(
        "/api/v1/sources",
        headers=headers,
        json={
            "name": "Bound HN",
            "type": "hackernews",
            "config_json": {},
            "enabled": True,
        },
    ).json()
    fixed_project = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Bound fixed connector",
            "source_type": "hackernews",
            "source_id": fixed["id"],
            "query": "ask",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    assert fixed_project.status_code == 200
    changed_type = client.patch(
        f"/api/v1/sources/{fixed['id']}",
        headers=headers,
        json={
            "name": "Bound HN",
            "type": "github",
            "config_json": {},
            "enabled": True,
        },
    )
    assert changed_type.status_code == 409

    discourse = create_discourse_source(client, headers)
    authorize_source(client, discourse["id"], headers)

    response = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Wrong connector",
            "source_type": "hackernews",
            "source_id": discourse["id"],
            "query": "ask",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    assert response.status_code == 409
