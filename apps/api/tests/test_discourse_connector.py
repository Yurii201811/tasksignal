from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from app.services.ingestion.connectors import DiscourseConnector, DiscourseConnectorError
from app.services.ingestion.normalization import normalize

PUBLIC_ADDRESS = "93.184.216.34"


def public_resolver(host: str, port: int) -> list[str]:
    assert host == "forum.example"
    assert port == 443
    return [PUBLIC_ADDRESS]


def connector_for(
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: object,
) -> DiscourseConnector:
    return DiscourseConnector(
        "https://forum.example",
        resolver=public_resolver,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://forum.example",
        "https://user:password@forum.example",
        "https://127.0.0.1",
        "https://[::1]",
        "https://forum.example/private/path",
        "https://forum.example?api_key=secret",
    ],
)
def test_discourse_rejects_non_public_base_origins(base_url: str) -> None:
    with pytest.raises(DiscourseConnectorError) as caught:
        DiscourseConnector(base_url, resolver=lambda _host, _port: [PUBLIC_ADDRESS])

    assert caught.value.info.category == "unsafe_configuration"
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.1",
        "127.0.0.1",
        "169.254.10.20",
        "172.16.0.1",
        "192.168.0.1",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
    ],
)
def test_discourse_rejects_non_public_dns_answers(address: str) -> None:
    with pytest.raises(DiscourseConnectorError) as caught:
        DiscourseConnector(
            "https://forum.example",
            resolver=lambda _host, _port: [address],
        )

    assert caught.value.info.category == "unsafe_configuration"


def test_discourse_latest_fetches_bounded_topic_details_and_redacts_authors() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        if request.url.path == "/latest.json":
            return httpx.Response(
                200,
                headers={"set-cookie": "session=must-not-be-replayed; Secure"},
                json={
                    "topic_list": {
                        "topics": [
                            {
                                "id": 42,
                                "slug": "manual-release-work",
                                "title": "Manual release work",
                                "created_at": "2026-07-11T10:00:00Z",
                                "posters": [{"user_id": 7, "description": "Original Poster"}],
                                "last_poster_username": "raw-list-author",
                                "posts_count": 3,
                                "views": 120,
                                "tags": ["workflow"],
                            }
                        ]
                    }
                },
            )
        assert request.url.path == "/t/42.json"
        return httpx.Response(
            200,
            json={
                "id": 42,
                "slug": "manual-release-work",
                "title": "Manual release work",
                "created_at": "2026-07-11T10:00:00Z",
                "tags": ["workflow", "release"],
                "views": 125,
                "posts_count": 3,
                "post_stream": {
                    "posts": [
                        {
                            "id": 900,
                            "username": "raw-topic-author",
                            "name": "Raw Real Name",
                            "cooked": "<p>Every release needs <strong>manual checks</strong>.</p>",
                            "created_at": "2026-07-11T10:00:00Z",
                            "like_count": 8,
                        }
                    ]
                },
            },
        )

    connector = connector_for(handler, max_results=5, max_topic_requests=1)
    result = connector.fetch_result(limit=50)

    assert result.requests_made == 2
    assert result.retry_after_seconds is None
    assert result.last_success_at is not None
    assert connector.last_result == result
    assert connector.last_error is None
    assert len(result.items) == 1
    item = result.items[0]
    assert item.source == "discourse"
    assert item.external_id == "https://forum.example/t/42"
    assert item.raw_json == {
        "title": "Manual release work",
        "body": "<p>Every release needs <strong>manual checks</strong>.</p>",
        "created_at": "2026-07-11T10:00:00Z",
        "url": "https://forum.example/t/manual-release-work/42",
        "tags": ["workflow", "release"],
        "score": 8,
        "comments_count": 2,
        "views": 125,
        "category_id": None,
    }
    serialized = json.dumps(item.raw_json)
    assert "raw-list-author" not in serialized
    assert "raw-topic-author" not in serialized
    assert "Raw Real Name" not in serialized

    normalized = normalize(item)
    assert normalized["title"] == "Manual release work"
    assert normalized["body"] == "Every release needs manual checks ."
    assert normalized["author_hash"] is None
    assert normalized["comments_count"] == 2
    assert normalized["url"] == "https://forum.example/t/manual-release-work/42"
    assert [request.url.path for request in requests] == ["/latest.json", "/t/42.json"]


def test_discourse_search_caps_results_and_topic_detail_requests() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/search.json":
            assert request.url.params["q"] == "manual reporting"
            return httpx.Response(
                200,
                json={
                    "topics": [
                        {
                            "id": topic_id,
                            "slug": f"topic-{topic_id}",
                            "title": f"Topic {topic_id}",
                            "excerpt": f"Summary {topic_id}",
                            "created_at": "2026-07-11T10:00:00Z",
                            "posts_count": topic_id,
                        }
                        for topic_id in range(1, 5)
                    ]
                },
            )
        assert request.url.path == "/t/1.json"
        return httpx.Response(
            200,
            json={
                "id": 1,
                "slug": "topic-1",
                "title": "Topic 1",
                "post_stream": {"posts": [{"cooked": "<p>Detailed body</p>"}]},
            },
        )

    connector = connector_for(handler, max_results=2, max_topic_requests=1)

    items = connector.fetch(query="manual reporting", limit=50)

    assert len(items) == 2
    assert items[0].raw_json["body"] == "<p>Detailed body</p>"
    assert items[1].raw_json["body"] == "Summary 2"
    assert paths == ["/search.json", "/t/1.json"]


def test_discourse_topic_identity_is_namespaced_by_authorized_origin() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "topic_list": {
                    "topics": [
                        {
                            "id": 42,
                            "slug": "same-id",
                            "title": "Forum-specific topic",
                            "excerpt": "Public evidence",
                        }
                    ]
                }
            },
        )

    def make(origin: str) -> DiscourseConnector:
        return DiscourseConnector(
            origin,
            resolver=lambda _host, _port: [PUBLIC_ADDRESS],
            transport=httpx.MockTransport(handler),
            max_topic_requests=0,
        )

    first = make("https://forum.example").fetch()[0]
    second = make("https://other.example").fetch()[0]

    assert first.external_id == "https://forum.example/t/42"
    assert second.external_id == "https://other.example/t/42"
    assert first.external_id != second.external_id


def test_discourse_allows_only_same_origin_redirects() -> None:
    safe_paths: list[str] = []

    def same_origin_handler(request: httpx.Request) -> httpx.Response:
        safe_paths.append(request.url.path)
        if request.url.path == "/latest.json" and "page" not in request.url.params:
            return httpx.Response(302, headers={"location": "/latest.json?page=1"})
        return httpx.Response(200, json={"topic_list": {"topics": []}})

    result = connector_for(same_origin_handler).fetch_result()
    assert result.items == []
    assert result.requests_made == 2
    assert safe_paths == ["/latest.json", "/latest.json"]

    for location in (
        "https://evil.example/latest.json",
        "https://forum.example:444/latest.json",
        "http://forum.example/latest.json",
        "//evil.example/latest.json",
    ):
        attempts = 0

        def cross_origin_handler(
            request: httpx.Request,
            redirect_location: str = location,
        ) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(302, headers={"location": redirect_location})

        connector = connector_for(cross_origin_handler)
        with pytest.raises(DiscourseConnectorError) as caught:
            connector.fetch()
        assert caught.value.info.category == "unsafe_redirect"
        assert attempts == 1


def test_discourse_pins_connection_to_validated_ip_during_dns_rebinding() -> None:
    connected_addresses: list[str] = []
    sent_host_headers: list[str] = []
    sent_sni_names: list[str | None] = []

    def rebinding_transport(request: httpx.Request) -> httpx.Response:
        # A normal hostname transport resolves again at connect time. Simulate
        # that second answer rebinding to loopback; an IP-targeted request does
        # not perform the attacker-controlled hostname lookup again.
        connected_address = (
            "127.0.0.1" if request.url.host == "forum.example" else request.url.host
        )
        connected_addresses.append(connected_address)
        sent_host_headers.append(request.headers["host"])
        sent_sni_names.append(request.extensions.get("sni_hostname"))
        return httpx.Response(200, json={"topic_list": {"topics": []}})

    connector = connector_for(rebinding_transport)

    connector.fetch()

    assert connected_addresses == [PUBLIC_ADDRESS]
    assert sent_host_headers == ["forum.example"]
    assert sent_sni_names == ["forum.example"]


def test_discourse_rejects_oversized_and_malformed_responses() -> None:
    oversized = connector_for(
        lambda _request: httpx.Response(200, content=b"x" * 129),
        max_response_bytes=128,
    )
    with pytest.raises(DiscourseConnectorError) as caught:
        oversized.fetch()
    assert caught.value.info.category == "response_too_large"

    malformed = connector_for(
        lambda _request: httpx.Response(200, content=b"{not-json"),
    )
    with pytest.raises(DiscourseConnectorError) as caught:
        malformed.fetch()
    assert caught.value.info.category == "malformed_response"


def test_discourse_captures_retry_after_without_sleeping() -> None:
    connector = connector_for(
        lambda _request: httpx.Response(429, headers={"retry-after": "120"}),
    )

    with pytest.raises(DiscourseConnectorError) as caught:
        connector.fetch()

    assert caught.value.info.category == "rate_limited"
    assert caught.value.info.status_code == 429
    assert caught.value.info.retry_after_seconds == 120
    assert caught.value.info.retriable is True
    assert connector.last_error == caught.value.info


def test_discourse_pathological_retry_after_remains_a_typed_failure() -> None:
    connector = connector_for(
        lambda _request: httpx.Response(429, headers={"retry-after": "1e309"}),
    )

    with pytest.raises(DiscourseConnectorError) as caught:
        connector.fetch()

    assert caught.value.info.category == "rate_limited"
    assert caught.value.info.status_code == 429
    assert caught.value.info.retry_after_seconds is None


def test_discourse_wraps_timeouts_in_typed_sanitized_errors() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out with token=do-not-leak", request=request)

    connector = connector_for(timeout_handler, timeout_seconds=0.5)

    with pytest.raises(DiscourseConnectorError) as caught:
        connector.fetch()

    assert caught.value.info.category == "timeout"
    assert caught.value.info.retriable is True
    assert "do-not-leak" not in caught.value.info.message


def test_discourse_rejects_empty_or_malformed_topic_payloads() -> None:
    malformed_payloads = [[], {"topic_list": {"topics": "not-a-list"}}, {"topics": [{}]}]

    for payload in malformed_payloads:
        connector = connector_for(lambda _request, payload=payload: httpx.Response(200, json=payload))
        with pytest.raises(DiscourseConnectorError) as caught:
            connector.fetch()
        assert caught.value.info.category == "malformed_response"


def test_discourse_wraps_pathologically_deep_json_as_malformed() -> None:
    deeply_nested = b'{"topics":' + (b"[" * 1200) + (b"]" * 1200) + b"}"
    connector = connector_for(
        lambda _request: httpx.Response(200, content=deeply_nested),
    )

    with pytest.raises(DiscourseConnectorError) as caught:
        connector.fetch()

    assert caught.value.info.category == "malformed_response"
