from __future__ import annotations

from app.api import routes
from app.services.ingestion.connectors import (
    DiscourseConnector,
    DiscourseConnectorError,
)
from app.services.ingestion.types import (
    ConnectorFailure,
    ConnectorFetchResult,
    RawFetchedItem,
    utc_now,
)
from app.workers import scan_pipeline

OPERATOR_HEADERS = {"X-Operator-Scan-Token": "source-admin-token"}


def discourse_evidence(
    external_id: str,
    origin: str = "https://forum.example",
) -> RawFetchedItem:
    return RawFetchedItem(
        source="discourse",
        external_id=f"{origin}/t/{external_id}",
        raw_json={
            "title": f"Painful manual release workflow {external_id}",
            "body": (
                "Builders manually copy release failures every week. It takes forever "
                "and teams would pay for a focused workflow tool."
            ),
            "created_at": "2026-07-11T12:00:00Z",
            "url": f"{origin}/t/release/{external_id}",
            "tags": ["release", "workflow"],
            "score": 7,
            "comments_count": 3,
        },
        fetched_at=utc_now(),
    )


class StaticDiscourseConnector(DiscourseConnector):
    def __init__(
        self,
        items: list[RawFetchedItem],
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.items = items
        self.retry_after_seconds = retry_after_seconds

    def fetch_result(self, query: str = "", limit: int = 50) -> ConnectorFetchResult:
        return ConnectorFetchResult(
            items=self.items[:limit],
            requests_made=1,
            retry_after_seconds=self.retry_after_seconds,
            last_success_at=utc_now(),
        )


class RateLimitedDiscourseConnector(DiscourseConnector):
    def __init__(self) -> None:
        pass

    def fetch_result(self, query: str = "", limit: int = 50) -> ConnectorFetchResult:
        raise DiscourseConnectorError(
            ConnectorFailure(
                category="rate_limited",
                message="Discourse returned HTTP 429.",
                status_code=429,
                retry_after_seconds=120,
                retriable=True,
            )
        )


def create_authorized_project(client, monkeypatch) -> tuple[dict, dict]:
    monkeypatch.setattr(routes.settings, "operator_scan_token", "source-admin-token")
    monkeypatch.setattr(
        routes.settings,
        "public_scan_sources",
        "fixture,hackernews,discourse",
    )
    source_response = client.post(
        "/api/v1/sources",
        headers=OPERATOR_HEADERS,
        json={
            "name": "Builder Forum",
            "type": "discourse",
            "config_json": {},
            "enabled": True,
        },
    )
    assert source_response.status_code == 200, source_response.text
    source = source_response.json()
    authorization = client.put(
        f"/api/v1/sources/{source['id']}/authorization",
        headers=OPERATOR_HEADERS,
        json={"origin": "https://forum.example", "terms_confirmed": True},
    )
    assert authorization.status_code == 200, authorization.text
    project_response = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Forum research",
            "source_type": "discourse",
            "source_id": source["id"],
            "query": "manual release",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    assert project_response.status_code == 200, project_response.text
    return source, project_response.json()


def test_discourse_project_run_snapshots_origin_and_runtime_success(
    client,
    monkeypatch,
) -> None:
    source, project = create_authorized_project(client, monkeypatch)
    connector = StaticDiscourseConnector(
        [discourse_evidence("101"), discourse_evidence("102")]
    )

    def connector_for_source(source_type: str, **kwargs):
        assert source_type == "discourse"
        assert str(kwargs["source_id"]) == source["id"]
        return connector

    monkeypatch.setattr(scan_pipeline, "connector_for_source", connector_for_source)

    missing_operator = client.post(
        f"/api/v1/research-projects/{project['id']}/run"
    )
    public_endpoint = client.post(
        "/api/v1/scans",
        json={
            "source": "discourse",
            "source_id": source["id"],
            "query": "manual release",
            "limit": 10,
        },
    )
    assert missing_operator.status_code == 403
    assert public_endpoint.status_code == 403

    first = client.post(
        f"/api/v1/research-projects/{project['id']}/run",
        headers=OPERATOR_HEADERS,
    )
    second = client.post(
        f"/api/v1/research-projects/{project['id']}/run",
        headers=OPERATOR_HEADERS,
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "completed"
    assert first.json()["source_id"] == source["id"]
    assert second.json()["items_saved"] == 0
    runs = client.get(f"/api/v1/research-projects/{project['id']}/runs").json()
    assert [run["source_origin"] for run in runs] == [
        "https://forum.example",
        "https://forum.example",
    ]
    runtime = client.get(f"/api/v1/sources/{source['id']}/runtime-state").json()
    assert runtime["readiness"] == "ready"
    assert runtime["can_run"] is True
    assert runtime["last_success_at"] is not None
    assert runtime["last_failure_at"] is None


def test_discourse_rate_limit_is_sanitized_persisted_and_blocks_retry(
    client,
    monkeypatch,
) -> None:
    source, project = create_authorized_project(client, monkeypatch)
    monkeypatch.setattr(
        scan_pipeline,
        "connector_for_source",
        lambda *_args, **_kwargs: RateLimitedDiscourseConnector(),
    )

    failed = client.post(
        f"/api/v1/research-projects/{project['id']}/run",
        headers=OPERATOR_HEADERS,
    )

    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    runtime = client.get(f"/api/v1/sources/{source['id']}/runtime-state").json()
    assert runtime["readiness"] == "retry_later"
    assert runtime["can_run"] is False
    assert runtime["last_failure_code"] == "rate_limited"
    assert runtime["last_http_status"] == 429
    assert runtime["retry_after_at"] is not None
    assert "429" in runtime["last_failure_message"]

    retry = client.post(
        f"/api/v1/research-projects/{project['id']}/run",
        headers=OPERATOR_HEADERS,
    )
    assert retry.status_code == 409
    assert "retry_later" in retry.json()["detail"]


def test_discourse_successful_retry_after_paces_the_next_run(
    client,
    monkeypatch,
) -> None:
    source, project = create_authorized_project(client, monkeypatch)
    monkeypatch.setattr(
        scan_pipeline,
        "connector_for_source",
        lambda *_args, **_kwargs: StaticDiscourseConnector(
            [discourse_evidence("paced")],
            retry_after_seconds=120,
        ),
    )

    completed = client.post(
        f"/api/v1/research-projects/{project['id']}/run",
        headers=OPERATOR_HEADERS,
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    runtime = client.get(f"/api/v1/sources/{source['id']}/runtime-state").json()
    assert runtime["readiness"] == "retry_later"
    assert runtime["last_success_at"] is not None
    assert runtime["retry_after_at"] is not None

    blocked = client.post(
        f"/api/v1/research-projects/{project['id']}/run",
        headers=OPERATOR_HEADERS,
    )
    assert blocked.status_code == 409


def test_cross_forum_duplicate_content_keeps_each_run_origin(
    client,
    monkeypatch,
) -> None:
    first_source, project = create_authorized_project(client, monkeypatch)
    second_source_response = client.post(
        "/api/v1/sources",
        headers=OPERATOR_HEADERS,
        json={
            "name": "Other Builder Forum",
            "type": "discourse",
            "config_json": {},
            "enabled": True,
        },
    )
    assert second_source_response.status_code == 200
    second_source = second_source_response.json()
    second_authorization = client.put(
        f"/api/v1/sources/{second_source['id']}/authorization",
        headers=OPERATOR_HEADERS,
        json={"origin": "https://other.example", "terms_confirmed": True},
    )
    assert second_authorization.status_code == 200

    origins = {
        first_source["id"]: "https://forum.example",
        second_source["id"]: "https://other.example",
    }

    def connector_for_source(_source_type: str, **kwargs):
        origin = origins[str(kwargs["source_id"])]
        return StaticDiscourseConnector(
            [
                discourse_evidence("42", origin),
                discourse_evidence("43", origin),
            ]
        )

    monkeypatch.setattr(scan_pipeline, "connector_for_source", connector_for_source)
    first = client.post(
        f"/api/v1/research-projects/{project['id']}/run",
        headers=OPERATOR_HEADERS,
    )
    assert first.status_code == 200
    switched = client.patch(
        f"/api/v1/research-projects/{project['id']}",
        json={"source_id": second_source["id"]},
    )
    assert switched.status_code == 200, switched.text
    second = client.post(
        f"/api/v1/research-projects/{project['id']}/run",
        headers=OPERATOR_HEADERS,
    )
    assert second.status_code == 200
    assert client.get("/api/v1/stats").json()["total_items"] == 2

    runs = client.get(f"/api/v1/research-projects/{project['id']}/runs").json()
    assert [run["source_origin"] for run in runs] == [
        "https://other.example",
        "https://forum.example",
    ]
    delta = client.get(
        f"/api/v1/research-projects/{project['id']}/runs/{runs[0]['id']}/delta"
    ).json()["evidence_changes"]
    assert delta == {
        "new": 0,
        "seen_before": 2,
        "updated": 0,
        "unchanged": 0,
        "not_observed_this_run": 2,
    }

    search = client.post(
        "/api/v1/search",
        json={
            "query": "manual release workflow",
            "project_id": project["id"],
            "limit": 10,
        },
    )
    assert search.status_code == 200, search.text
    evidence_hit = search.json()["evidence_hits"][0]
    assert evidence_hit["source_url"].startswith("https://other.example/")
    observation_urls = [
        observation["source_url"]
        for observation in evidence_hit["provenance"]["observations"]
    ]
    assert len(observation_urls) == 2
    assert observation_urls[0].startswith("https://other.example/")
    assert observation_urls[1].startswith("https://forum.example/")

    thread = client.get(
        f"/api/v1/opportunity-threads?project_id={project['id']}"
    ).json()[0]
    assert thread["current_snapshot"]["evidence_items"][0]["url"].startswith(
        "https://other.example/"
    )
