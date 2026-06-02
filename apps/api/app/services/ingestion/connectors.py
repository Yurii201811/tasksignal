from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.services.ingestion.types import RawFetchedItem, utc_now


class ConnectorError(RuntimeError):
    pass


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


def connector_display_name(source_type: str) -> str:
    names: dict[str, str] = {
        "fixture": "Fixture files",
        "github": "GitHub Issues",
        "hackernews": "Hacker News",
        "reddit": "Reddit",
        "stackexchange": "Stack Exchange",
    }
    return names.get(source_type, source_type.replace("_", " ").title())


SOURCE_GUIDANCE: dict[str, str] = {
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
    (re.compile(r"Authorization:\s*\S+", re.IGNORECASE), "Authorization: [redacted secret]"),
    (
        re.compile(
            r"(client_secret|access_token|api_key|password|token)=[^\s&]+",
            re.IGNORECASE,
        ),
        r"\1=[redacted secret]",
    ),
    (re.compile(r"token=[^\s&]+", re.IGNORECASE), "token=[redacted secret]"),
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
