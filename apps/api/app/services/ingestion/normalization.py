from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from html import unescape
from typing import Any
from urllib.parse import parse_qsl, urlparse

from app.core.config import settings
from app.services.ingestion.types import RawFetchedItem

TAG_RE = re.compile(r"<[^>]+>")
SENSITIVE_URL_PARAMETER_KEYS = {
    "accesskey",
    "accesstoken",
    "apikey",
    "auth",
    "authorization",
    "code",
    "cookie",
    "credential",
    "key",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
    "xamzcredential",
    "xamzsecuritytoken",
    "xamzsignature",
}


def clean_text(value: str | None) -> str:
    text = TAG_RE.sub(" ", unescape(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str) and value:
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def hash_author(author: str | None) -> str | None:
    if not author:
        return None
    digest = hashlib.sha256(f"{settings.author_hash_salt}:{author}".encode()).hexdigest()
    return digest[:24]


def text_hash(title: str, body: str) -> str:
    normalized = re.sub(r"\s+", " ", f"{title} {body}".lower()).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _has_sensitive_url_parameters(value: str) -> bool:
    for key, _value in parse_qsl(value.lstrip("?#"), keep_blank_values=True):
        normalized_key = re.sub(r"[^a-z0-9]", "", key.casefold())
        if normalized_key in SENSITIVE_URL_PARAMETER_KEYS or normalized_key.endswith(
            ("apikey", "credential", "password", "secret", "signature", "token")
        ):
            return True
    return False


def safe_source_url(value: Any, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback

    candidate = value.strip()
    if not candidate:
        return fallback

    parsed = urlparse(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        return fallback
    if _has_sensitive_url_parameters(parsed.query) or _has_sensitive_url_parameters(
        parsed.fragment
    ):
        return fallback
    if parsed.hostname:
        return candidate
    return fallback


def normalize(raw: RawFetchedItem) -> dict[str, Any]:
    item = raw.raw_json
    source = raw.source

    if source == "reddit":
        title = clean_text(item.get("title"))
        body = clean_text(item.get("body") or item.get("selftext"))
        author = item.get("author")
        created = parse_datetime(item.get("created_at") or item.get("created_utc"))
        url = safe_source_url(
            item.get("url"),
            fallback=f"https://reddit.com/comments/{raw.external_id}",
        )
        tags = item.get("tags") or item.get("subreddit") and [item.get("subreddit")] or []
    elif source == "hackernews":
        title = clean_text(item.get("title"))
        body = clean_text(item.get("body") or item.get("text") or item.get("url"))
        author = item.get("by")
        created = parse_datetime(item.get("created_at") or item.get("time"))
        url = safe_source_url(
            item.get("url"),
            fallback=f"https://news.ycombinator.com/item?id={raw.external_id}",
        )
        tags = item.get("tags") or ["hackernews"]
    elif source == "github":
        title = clean_text(item.get("title"))
        body = clean_text(item.get("body"))
        author = (
            (item.get("user") or {}).get("login")
            if isinstance(item.get("user"), dict)
            else item.get("author")
        )
        created = parse_datetime(item.get("created_at"))
        url = safe_source_url(item.get("html_url") or item.get("url"))
        tags = [
            label["name"] if isinstance(label, dict) else str(label)
            for label in item.get("labels", [])
        ]
    elif source == "stackexchange":
        title = clean_text(item.get("title"))
        body = clean_text(item.get("body") or item.get("excerpt"))
        owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
        author = owner.get("display_name") or item.get("author")
        created = parse_datetime(item.get("creation_date") or item.get("created_at"))
        url = safe_source_url(item.get("link"))
        tags = item.get("tags") or []
    elif source == "discourse":
        title = clean_text(item.get("title"))
        body = clean_text(item.get("body") or item.get("excerpt"))
        author = None
        created = parse_datetime(item.get("created_at"))
        url = safe_source_url(item.get("url"))
        tags = item.get("tags") or []
    else:
        title = clean_text(item.get("title"))
        body = clean_text(item.get("body") or item.get("text"))
        author = item.get("author")
        created = parse_datetime(item.get("created_at"))
        url = safe_source_url(item.get("url"))
        tags = item.get("tags") or []

    return {
        "source": source,
        "external_id": raw.external_id,
        "url": url,
        "title": title,
        "body": body,
        "author_hash": hash_author(author),
        "score": item.get("score"),
        "comments_count": (
            item.get("comments_count")
            or item.get("num_comments")
            or item.get("comments")
            or item.get("descendants")
            or item.get("answer_count")
        ),
        "created_at": created,
        "fetched_at": raw.fetched_at,
        "tags": tags,
        "text_hash": text_hash(title, body),
        "language": "en",
    }
