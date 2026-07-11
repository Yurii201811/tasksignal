from __future__ import annotations

import json
import math
import re
import socket
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import httpx

from app.core.config import settings
from app.services.ingestion.types import (
    ConnectorFailure,
    ConnectorFetchResult,
    RawFetchedItem,
    utc_now,
)


class ConnectorError(RuntimeError):
    pass


class DiscourseConnectorError(ConnectorError):
    """A Discourse failure carrying only sanitized, recordable metadata."""

    def __init__(self, info: ConnectorFailure) -> None:
        self.info = info
        super().__init__(info.message)


class BaseConnector(ABC):
    name: str

    @abstractmethod
    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        raise NotImplementedError


class FixtureConnector(BaseConnector):
    name = "fixture"

    def __init__(self, fixture_dir: Path | None = None) -> None:
        self.fixture_dir = fixture_dir or settings.fixture_dir

    def fetch(self, query: str = "", limit: int = 200) -> list[RawFetchedItem]:
        items: list[RawFetchedItem] = []
        for path in sorted(self.fixture_dir.glob("*_sample.json")):
            payload = json.loads(path.read_text())
            source = payload.get("source", path.stem.replace("_sample", ""))
            for raw in payload.get("items", []):
                if query and query.lower() not in json.dumps(raw).lower():
                    continue
                items.append(
                    RawFetchedItem(
                        source=source,
                        external_id=str(raw.get("external_id") or raw.get("id")),
                        raw_json=raw,
                        fetched_at=utc_now(),
                    )
                )
                if len(items) >= limit:
                    return items
        return items


class RedditConnector(BaseConnector):
    name = "reddit"

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        if not all(
            [
                settings.reddit_client_id,
                settings.reddit_client_secret,
                settings.reddit_user_agent,
            ]
        ):
            raise ConnectorError(
                "Reddit credentials are missing. Set REDDIT_CLIENT_ID, "
                "REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT."
            )

        with httpx.Client(timeout=20, headers={"User-Agent": settings.reddit_user_agent}) as client:
            token_response = client.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=(settings.reddit_client_id, settings.reddit_client_secret),
                data={"grant_type": "client_credentials"},
            )
            token_response.raise_for_status()
            token = token_response.json().get("access_token")
            if not token:
                raise ConnectorError("Reddit OAuth did not return an access token.")

            response = client.get(
                "https://oauth.reddit.com/search",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "q": query or "manual workflow automation",
                    "limit": min(limit, 100),
                    "sort": "new",
                    "restrict_sr": "false",
                    "type": "link",
                },
            )
            response.raise_for_status()

        items: list[RawFetchedItem] = []
        for child in response.json().get("data", {}).get("children", []):
            data = child.get("data", {})
            if not isinstance(data, dict):
                continue
            external_id = str(data.get("id") or data.get("name") or "")
            if not external_id:
                continue
            permalink = data.get("permalink") or ""
            source_url = (
                f"https://www.reddit.com{permalink}"
                if permalink.startswith("/")
                else data.get("url", "")
            )
            items.append(
                RawFetchedItem(
                    source="reddit",
                    external_id=external_id,
                    raw_json={
                        "title": data.get("title"),
                        "body": data.get("selftext"),
                        "selftext": data.get("selftext"),
                        "author": data.get("author"),
                        "created_utc": data.get("created_utc"),
                        "url": source_url,
                        "subreddit": data.get("subreddit"),
                        "score": data.get("score"),
                        "comments_count": data.get("num_comments"),
                    },
                    fetched_at=utc_now(),
                )
            )
        return items


class HackerNewsConnector(BaseConnector):
    name = "hackernews"

    def fetch(self, query: str = "ask", limit: int = 30) -> list[RawFetchedItem]:
        endpoints = {
            "ask": "askstories",
            "best": "beststories",
            "job": "jobstories",
            "new": "newstories",
            "show": "showstories",
            "top": "topstories",
        }
        normalized_query = query.strip().lower() or "ask"
        endpoint = endpoints.get(normalized_query, "askstories")
        filter_text = "" if normalized_query in endpoints else normalized_query
        fetch_budget = min(max(limit * 5, limit), 250) if filter_text else limit

        with httpx.Client(timeout=10) as client:
            response = client.get(f"https://hacker-news.firebaseio.com/v0/{endpoint}.json")
            response.raise_for_status()
            ids = response.json()

            items: list[RawFetchedItem] = []
            for story_id in ids[:fetch_budget]:
                story_response = client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                )
                story_response.raise_for_status()
                story = story_response.json()
                if not story or story.get("deleted") or story.get("dead"):
                    continue
                if filter_text and filter_text not in json.dumps(story).lower():
                    continue
                items.append(
                    RawFetchedItem(
                        source="hackernews",
                        external_id=str(story_id),
                        raw_json=story,
                        fetched_at=utc_now(),
                    )
                )
                if len(items) >= limit:
                    break
        return items


class GitHubIssuesConnector(BaseConnector):
    name = "github"

    def fetch(self, query: str = "label:bug", limit: int = 30) -> list[RawFetchedItem]:
        headers = {"Accept": "application/vnd.github+json"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        response = httpx.get(
            "https://api.github.com/search/issues",
            params={"q": query, "per_page": min(limit, 100)},
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        return [
            RawFetchedItem(
                source="github",
                external_id=str(item["id"]),
                raw_json=item,
                fetched_at=utc_now(),
            )
            for item in response.json().get("items", [])
        ]


class StackExchangeConnector(BaseConnector):
    name = "stackexchange"

    def fetch(self, query: str = "automation", limit: int = 30) -> list[RawFetchedItem]:
        params = {
            "order": "desc",
            "sort": "activity",
            "site": "stackoverflow",
            "intitle": query,
            "pagesize": min(limit, 100),
            "filter": "withbody",
        }
        if settings.stack_exchange_key:
            params["key"] = settings.stack_exchange_key
        response = httpx.get("https://api.stackexchange.com/2.3/search/advanced", params=params, timeout=15)
        response.raise_for_status()
        return [
            RawFetchedItem(
                source="stackexchange",
                external_id=str(item["question_id"]),
                raw_json=item,
                fetched_at=utc_now(),
            )
            for item in response.json().get("items", [])
        ]


DiscourseResolver = Callable[[str, int], Iterable[str]]


@dataclass
class _DiscourseFetchState:
    requests_made: int = 0
    retry_after_seconds: int | None = None


def _system_resolver(host: str, port: int) -> list[str]:
    addresses = {
        sockaddr[0]
        for _family, _type, _proto, _canonname, sockaddr in socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
        )
    }
    return sorted(addresses)


def _discourse_error(
    category: str,
    message: str,
    *,
    status_code: int | None = None,
    retry_after_seconds: int | None = None,
    retriable: bool = False,
) -> DiscourseConnectorError:
    return DiscourseConnectorError(
        ConnectorFailure(
            category=category,
            message=message,
            status_code=status_code,
            retry_after_seconds=retry_after_seconds,
            retriable=retriable,
        )
    )


class DiscourseConnector(BaseConnector):
    """Read-only connector for an explicitly authorized public Discourse origin."""

    name = "discourse"
    _REDIRECT_STATUSES = {301, 302, 303, 307, 308}

    def __init__(
        self,
        base_url: str,
        *,
        resolver: DiscourseResolver | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 10.0,
        max_response_bytes: int = 2_000_000,
        max_results: int = 50,
        max_topic_requests: int = 10,
        max_redirects: int = 3,
    ) -> None:
        self._resolver = resolver or _system_resolver
        self._transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_results = max_results
        self.max_topic_requests = max_topic_requests
        self.max_redirects = max_redirects
        self.last_result: ConnectorFetchResult | None = None
        self.last_error: ConnectorFailure | None = None

        if (
            timeout_seconds <= 0
            or max_response_bytes <= 0
            or max_results <= 0
            or max_topic_requests < 0
            or max_redirects < 0
        ):
            raise _discourse_error(
                "unsafe_configuration",
                "Discourse connector limits must be positive and bounded.",
            )

        parsed = self._parse_url(base_url, category="unsafe_configuration")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise _discourse_error(
                "unsafe_configuration",
                "Discourse base URL must contain only an HTTPS origin.",
            )

        host = self._normalized_host(parsed.hostname)
        if self._is_ip_literal(host):
            raise _discourse_error(
                "unsafe_configuration",
                "Discourse base URL must use a public DNS hostname, not an IP literal.",
            )

        port = self._effective_port(parsed, category="unsafe_configuration")
        self._host = host
        self._port = port
        self._ensure_public_dns(category="unsafe_configuration")
        port_suffix = "" if port == 443 else f":{port}"
        self._authority = f"{host}{port_suffix}"
        self.base_url = f"https://{host}{port_suffix}"

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        return self.fetch_result(query=query, limit=limit).items

    def fetch_result(self, query: str = "", limit: int = 50) -> ConnectorFetchResult:
        self.last_error = None
        self.last_result = None
        state = _DiscourseFetchState()
        effective_limit = min(max(int(limit), 0), self.max_results)

        if effective_limit == 0:
            result = ConnectorFetchResult(
                items=[],
                requests_made=0,
                retry_after_seconds=None,
                last_success_at=utc_now(),
            )
            self.last_result = result
            return result

        try:
            result = self._fetch_result(query.strip(), effective_limit, state)
        except DiscourseConnectorError as exc:
            self.last_error = exc.info
            raise
        except httpx.TimeoutException as exc:
            error = _discourse_error(
                "timeout",
                "Discourse request exceeded the configured timeout.",
                retriable=True,
            )
            self.last_error = error.info
            raise error from exc
        except httpx.RequestError as exc:
            error = _discourse_error(
                "network_error",
                "Discourse request failed before a public response was received.",
                retriable=True,
            )
            self.last_error = error.info
            raise error from exc

        self.last_result = result
        return result

    def _fetch_result(
        self,
        query: str,
        effective_limit: int,
        state: _DiscourseFetchState,
    ) -> ConnectorFetchResult:
        timeout = httpx.Timeout(self.timeout_seconds)
        with httpx.Client(
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "TaskSignal/1.0 public-discourse-connector",
            },
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        ) as client:
            if query:
                payload = self._get_json(
                    client,
                    f"{self.base_url}/search.json",
                    params={"q": query},
                    state=state,
                )
            else:
                payload = self._get_json(
                    client,
                    f"{self.base_url}/latest.json",
                    params=None,
                    state=state,
                )

            topics = self._extract_topics(payload)[:effective_limit]
            items: list[RawFetchedItem] = []
            detail_budget = min(len(topics), self.max_topic_requests)
            for index, topic in enumerate(topics):
                topic_id = self._topic_id(topic)
                detail: dict[str, Any] | None = None
                if index < detail_budget:
                    detail = self._get_json(
                        client,
                        f"{self.base_url}/t/{topic_id}.json",
                        params=None,
                        state=state,
                    )
                    detail_id = detail.get("id")
                    if detail_id is not None and str(detail_id) != topic_id:
                        raise _discourse_error(
                            "malformed_response",
                            "Discourse topic detail did not match the requested topic.",
                        )
                items.append(self._to_raw_item(topic, detail))

        return ConnectorFetchResult(
            items=items,
            requests_made=state.requests_made,
            retry_after_seconds=state.retry_after_seconds,
            last_success_at=utc_now(),
        )

    def _get_json(
        self,
        client: httpx.Client,
        url: str,
        *,
        params: dict[str, str] | None,
        state: _DiscourseFetchState,
    ) -> dict[str, Any]:
        current_url = url
        current_params = params

        for redirect_count in range(self.max_redirects + 1):
            approved_addresses = self._validate_request_url(
                current_url,
                category="unsafe_target",
            )
            client.cookies.clear()
            request = client.build_request("GET", current_url, params=current_params)
            logical_request_url = str(request.url)
            request.url = request.url.copy_with(host=approved_addresses[0])
            request.headers["Host"] = self._authority
            request.extensions["sni_hostname"] = self._host
            response = client.send(request, stream=True)
            state.requests_made += 1

            try:
                retry_after = self._parse_retry_after(response.headers.get("retry-after"))
                if retry_after is not None:
                    state.retry_after_seconds = max(
                        state.retry_after_seconds or 0,
                        retry_after,
                    )

                if response.status_code in self._REDIRECT_STATUSES:
                    if redirect_count >= self.max_redirects:
                        raise _discourse_error(
                            "too_many_redirects",
                            "Discourse exceeded the configured redirect limit.",
                        )
                    location = response.headers.get("location")
                    if not location:
                        raise _discourse_error(
                            "malformed_response",
                            "Discourse returned a redirect without a location.",
                        )
                    redirected_url = urljoin(logical_request_url, location)
                    self._validate_request_url(redirected_url, category="unsafe_redirect")
                    current_url = redirected_url
                    current_params = None
                    continue

                if response.status_code >= 400:
                    is_rate_limited = response.status_code == 429
                    retriable = is_rate_limited or response.status_code in {408, 425} or (
                        response.status_code >= 500
                    )
                    raise _discourse_error(
                        "rate_limited" if is_rate_limited else "http_error",
                        f"Discourse returned HTTP {response.status_code}.",
                        status_code=response.status_code,
                        retry_after_seconds=retry_after,
                        retriable=retriable,
                    )

                body = self._read_bounded_body(response)
                try:
                    payload = json.loads(body)
                except (json.JSONDecodeError, RecursionError, UnicodeDecodeError) as exc:
                    raise _discourse_error(
                        "malformed_response",
                        "Discourse returned malformed JSON.",
                    ) from exc
                if not isinstance(payload, dict):
                    raise _discourse_error(
                        "malformed_response",
                        "Discourse JSON response must be an object.",
                    )
                return payload
            finally:
                response.close()
                client.cookies.clear()

        raise _discourse_error(
            "too_many_redirects",
            "Discourse exceeded the configured redirect limit.",
        )

    def _read_bounded_body(self, response: httpx.Response) -> bytes:
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = 0
            if declared_size > self.max_response_bytes:
                raise _discourse_error(
                    "response_too_large",
                    "Discourse response exceeded the configured byte limit.",
                )

        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > self.max_response_bytes:
                raise _discourse_error(
                    "response_too_large",
                    "Discourse response exceeded the configured byte limit.",
                )
        return bytes(content)

    def _validate_request_url(self, url: str, *, category: str) -> tuple[str, ...]:
        parsed = self._parse_url(url, category=category)
        host = self._normalized_host(parsed.hostname)
        port = self._effective_port(parsed, category=category)
        if host != self._host or port != self._port:
            raise _discourse_error(
                category,
                "Discourse requests must remain on the configured HTTPS origin.",
            )
        return self._ensure_public_dns(category=category)

    def _ensure_public_dns(self, *, category: str) -> tuple[str, ...]:
        try:
            addresses = list(self._resolver(self._host, self._port))
        except Exception as exc:
            raise _discourse_error(
                category,
                "Discourse hostname could not be resolved safely.",
                retriable=True,
            ) from exc

        if not addresses:
            raise _discourse_error(
                category,
                "Discourse hostname did not resolve to a public address.",
                retriable=True,
            )

        approved_addresses: set[str] = set()
        for value in addresses:
            try:
                address = ip_address(str(value).split("%", 1)[0])
            except ValueError as exc:
                raise _discourse_error(
                    category,
                    "Discourse hostname returned an invalid address.",
                ) from exc
            if (
                not address.is_global
                or address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            ):
                raise _discourse_error(
                    category,
                    "Discourse hostname resolved to a non-public address.",
                )
            approved_addresses.add(str(address))
        return tuple(
            sorted(
                approved_addresses,
                key=lambda value: (ip_address(value).version, value),
            )
        )

    @staticmethod
    def _parse_url(url: str, *, category: str) -> Any:
        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
        except (TypeError, ValueError) as exc:
            raise _discourse_error(
                category,
                "Discourse URL is not a valid HTTPS URL.",
            ) from exc
        if (
            parsed.scheme.lower() != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise _discourse_error(
                category,
                "Discourse URL must be a credential-free HTTPS URL.",
            )
        return parsed

    @staticmethod
    def _normalized_host(host: str | None) -> str:
        if not host:
            return ""
        try:
            return host.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise _discourse_error(
                "unsafe_configuration",
                "Discourse hostname is invalid.",
            ) from exc

    @staticmethod
    def _effective_port(parsed: Any, *, category: str) -> int:
        try:
            return parsed.port or 443
        except ValueError as exc:
            raise _discourse_error(
                category,
                "Discourse URL contains an invalid port.",
            ) from exc

    @staticmethod
    def _is_ip_literal(host: str) -> bool:
        try:
            ip_address(host)
        except ValueError:
            return False
        return True

    @staticmethod
    def _parse_retry_after(value: str | None) -> int | None:
        if not value:
            return None
        stripped = value.strip()
        if stripped.isascii() and stripped.isdigit():
            try:
                return max(0, int(stripped))
            except (OverflowError, ValueError):  # pragma: no cover - defensive bigint guard
                return None
        try:
            parsed = parsedate_to_datetime(stripped)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0, math.ceil((parsed - datetime.now(UTC)).total_seconds()))

    @staticmethod
    def _extract_topics(payload: dict[str, Any]) -> list[dict[str, Any]]:
        if "topic_list" in payload:
            topic_list = payload.get("topic_list")
            if not isinstance(topic_list, dict):
                raise _discourse_error(
                    "malformed_response",
                    "Discourse topic list is malformed.",
                )
            topics = topic_list.get("topics")
        else:
            topics = payload.get("topics")
        if not isinstance(topics, list):
            raise _discourse_error(
                "malformed_response",
                "Discourse response did not contain a topic list.",
            )
        if any(not isinstance(topic, dict) for topic in topics):
            raise _discourse_error(
                "malformed_response",
                "Discourse topic list contains malformed entries.",
            )
        return topics

    @staticmethod
    def _topic_id(topic: dict[str, Any]) -> str:
        raw_topic_id = topic.get("id")
        if isinstance(raw_topic_id, bool):
            raw_topic_id = None
        try:
            topic_id = int(raw_topic_id)
        except (TypeError, ValueError) as exc:
            raise _discourse_error(
                "malformed_response",
                "Discourse topic is missing a valid numeric ID.",
            ) from exc
        if topic_id <= 0:
            raise _discourse_error(
                "malformed_response",
                "Discourse topic is missing a valid numeric ID.",
            )
        return str(topic_id)

    def _to_raw_item(
        self,
        topic: dict[str, Any],
        detail: dict[str, Any] | None,
    ) -> RawFetchedItem:
        detail = detail or {}
        topic_id = self._topic_id(topic)
        post_stream = detail.get("post_stream")
        posts = post_stream.get("posts") if isinstance(post_stream, dict) else None
        first_post = posts[0] if isinstance(posts, list) and posts and isinstance(posts[0], dict) else {}

        title = detail.get("title") or topic.get("title") or ""
        body = (
            first_post.get("cooked")
            or first_post.get("raw")
            or detail.get("excerpt")
            or topic.get("excerpt")
            or ""
        )
        created_at = (
            first_post.get("created_at")
            or detail.get("created_at")
            or topic.get("created_at")
        )
        raw_tags = detail.get("tags") or topic.get("tags") or []
        tags = [str(tag) for tag in raw_tags if isinstance(tag, (str, int, float))]
        slug = detail.get("slug") or topic.get("slug") or "topic"
        safe_slug = quote(str(slug), safe="") or "topic"

        posts_count = detail.get("posts_count")
        if not isinstance(posts_count, int):
            posts_count = topic.get("posts_count")
        comments_count = detail.get("reply_count")
        if not isinstance(comments_count, int):
            comments_count = max(posts_count - 1, 0) if isinstance(posts_count, int) else None

        score = first_post.get("like_count")
        if not isinstance(score, (int, float)):
            score = detail.get("like_count") or topic.get("like_count")

        views = detail.get("views")
        if not isinstance(views, int):
            views = topic.get("views")

        return RawFetchedItem(
            source="discourse",
            external_id=f"{self.base_url}/t/{topic_id}",
            raw_json={
                "title": title if isinstance(title, str) else str(title),
                "body": body if isinstance(body, str) else "",
                "created_at": created_at,
                "url": f"{self.base_url}/t/{safe_slug}/{topic_id}",
                "tags": tags,
                "score": score,
                "comments_count": comments_count,
                "views": views,
                "category_id": detail.get("category_id") or topic.get("category_id"),
            },
            fetched_at=utc_now(),
        )


def connector_display_name(source_type: str) -> str:
    names: dict[str, str] = {
        "discourse": "Discourse",
        "fixture": "Fixture files",
        "github": "GitHub Issues",
        "hackernews": "Hacker News",
        "reddit": "Reddit",
        "stackexchange": "Stack Exchange",
    }
    return names.get(source_type, source_type.replace("_", " ").title())


SOURCE_GUIDANCE: dict[str, str] = {
    "discourse": (
        "Discourse scans use public JSON endpoints on one explicitly authorized HTTPS origin. "
        "No cookies or credentials are supported."
    ),
    "github": (
        "GitHub scans use the official Issues Search API. Set GITHUB_TOKEN for higher "
        "rate limits, or reduce the limit/query breadth."
    ),
    "hackernews": (
        "Hacker News scans use the public Firebase API and do not require credentials. "
        "Try a smaller limit or a feed query such as ask, new, top, best, show, or job."
    ),
    "reddit": (
        "Reddit scans require REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT. "
        "Configure them in .env and restart the API."
    ),
    "stackexchange": (
        "Stack Exchange scans use the official advanced search API. "
        "STACK_EXCHANGE_KEY is optional but helps with quota."
    ),
    "fixture": (
        "Fixture scans read local data/fixtures files. "
        "Confirm fixture files exist and are readable."
    ),
}

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Bearer\s+\S+", re.IGNORECASE), "Bearer [redacted secret]"),
    (
        re.compile(
            r"Authorization\s*:\s*"
            r"(?:(?:Bearer|Basic|Digest|Token|Negotiate|ApiKey)\s+)?[^\s,;]+",
            re.IGNORECASE,
        ),
        "Authorization: [redacted secret]",
    ),
    (
        re.compile(
            r"(client_secret|access_token|api_key|password|token)=[^\s&]+",
            re.IGNORECASE,
        ),
        r"\1=[redacted secret]",
    ),
]


def sanitize_error_message(value: object) -> str:
    text = " ".join(str(value).split())
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    if len(text) > 500:
        text = f"{text[:497].rstrip()}..."
    return text


def _http_status_hint(exc: httpx.HTTPStatusError) -> str:
    code = exc.response.status_code
    if code in (401, 403):
        return (
            "Credentials, authorization, or rate limits are likely involved. "
            "Check API keys and restart the API after updating .env."
        )
    if code == 429:
        return "Rate limit reached; lower the limit or add credentials if the connector supports them."
    return ""


def connector_failure_message(source_type: str, exc: Exception) -> str:
    display = connector_display_name(source_type)
    detail = sanitize_error_message(exc).rstrip(".!?")
    parts = [f"{display} scan failed: {detail}."]

    if isinstance(exc, httpx.HTTPStatusError):
        hint = _http_status_hint(exc)
        if hint:
            parts.append(hint)
    elif isinstance(
        exc,
        (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout, TimeoutError),
    ):
        parts.append("Network or service timeout; retry with a smaller limit.")

    elif "credentials" in detail.lower() or "unauthorized" in detail.lower():
        parts.append("Missing or invalid credentials; check setup guidance.")
    elif "rate limit" in detail.lower() or "too many requests" in detail.lower():
        parts.append("Rate limit exceeded; try again later or increase delay.")
    elif "empty" in detail.lower() or "no data" in detail.lower():
        parts.append("Scan completed but returned no results.")
    elif "unsupported" in detail.lower() or "database type" in detail.lower():
        parts.append("Unsupported database configuration or engine type.")

    guidance = SOURCE_GUIDANCE.get(source_type)
    if guidance:
        parts.append(guidance)
    return " ".join(parts)


def without_raw_author(source: str, item: dict[str, Any]) -> dict[str, Any]:
    if source == "discourse":
        return {
            "title": item.get("title"),
            "body": item.get("body"),
            "created_at": item.get("created_at"),
            "url": item.get("url"),
            "tags": item.get("tags") or [],
            "score": item.get("score"),
            "comments_count": item.get("comments_count"),
            "views": item.get("views"),
            "category_id": item.get("category_id"),
        }
    if source == "github":
        return {
            "title": item.get("title"),
            "body": item.get("body"),
            "created_at": item.get("created_at"),
            "html_url": item.get("html_url"),
            "url": item.get("url"),
            "labels": [
                {"name": label.get("name")}
                if isinstance(label, dict)
                else str(label)
                for label in item.get("labels", [])
            ],
            "score": item.get("score"),
            "comments_count": item.get("comments"),
            "state": item.get("state"),
        }
    if source == "hackernews":
        return {
            "title": item.get("title"),
            "text": item.get("text"),
            "time": item.get("time"),
            "url": item.get("url"),
            "score": item.get("score"),
            "descendants": item.get("descendants"),
            "type": item.get("type"),
        }
    if source == "reddit":
        return {
            "title": item.get("title"),
            "body": item.get("body") or item.get("selftext"),
            "selftext": item.get("selftext") or item.get("body"),
            "created_utc": item.get("created_utc"),
            "url": item.get("url"),
            "subreddit": item.get("subreddit"),
            "score": item.get("score"),
            "comments_count": item.get("comments_count") or item.get("num_comments"),
        }
    if source == "stackexchange":
        return {
            "title": item.get("title"),
            "body": item.get("body") or item.get("excerpt"),
            "creation_date": item.get("creation_date"),
            "created_at": item.get("created_at"),
            "link": item.get("link"),
            "tags": item.get("tags") or [],
            "score": item.get("score"),
            "answer_count": item.get("answer_count"),
            "is_answered": item.get("is_answered"),
        }
    return {
        key: value
        for key, value in item.items()
        if key not in {"author", "by", "display_name", "login", "user", "owner"}
    }
