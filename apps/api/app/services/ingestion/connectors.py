from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

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
        if not all([settings.reddit_client_id, settings.reddit_client_secret, settings.reddit_user_agent]):
            raise ConnectorError("Reddit credentials are missing. Use fixture mode or set Reddit OAuth env vars.")
        raise ConnectorError("Reddit OAuth flow is documented but not enabled in the MVP runner.")


class HackerNewsConnector(BaseConnector):
    name = "hackernews"

    def fetch(self, query: str = "ask", limit: int = 30) -> list[RawFetchedItem]:
        endpoint = "newstories" if query == "new" else "askstories"
        ids = httpx.get(f"https://hacker-news.firebaseio.com/v0/{endpoint}.json", timeout=10).json()
        items: list[RawFetchedItem] = []
        for story_id in ids[:limit]:
            story = httpx.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=10).json()
            if story:
                items.append(
                    RawFetchedItem(
                        source="hackernews",
                        external_id=str(story_id),
                        raw_json=story,
                        fetched_at=utc_now(),
                    )
                )
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

