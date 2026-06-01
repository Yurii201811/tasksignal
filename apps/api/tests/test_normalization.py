from app.services.ingestion.normalization import normalize
from app.services.ingestion.types import RawFetchedItem, utc_now


def test_normalization_hashes_author_and_text() -> None:
    item = normalize(
        RawFetchedItem(
            source="reddit",
            external_id="abc",
            raw_json={
                "title": "I hate manual CSV reports",
                "selftext": "Every week I export a spreadsheet.",
                "author": "raw-user",
                "created_at": "2026-04-20T00:00:00Z",
                "url": "https://example.com",
            },
            fetched_at=utc_now(),
        )
    )

    assert item["author_hash"] != "raw-user"
    assert len(item["text_hash"]) == 64
    assert item["source"] == "reddit"


def test_normalization_rejects_unsafe_source_url() -> None:
    item = normalize(
        RawFetchedItem(
            source="hackernews",
            external_id="123",
            raw_json={
                "title": "Manual reporting takes forever",
                "text": "I need a better workflow.",
                "by": "raw-user",
                "time": 1_780_000_000,
                "url": "data:text/html,<script>alert(1)</script>",
            },
            fetched_at=utc_now(),
        )
    )

    assert item["url"] == "https://news.ycombinator.com/item?id=123"


def test_normalization_keeps_safe_source_url() -> None:
    item = normalize(
        RawFetchedItem(
            source="github",
            external_id="456",
            raw_json={
                "title": "Manual deploy steps are painful",
                "body": "Every release requires copy paste checks.",
                "author": "raw-user",
                "created_at": "2026-04-20T00:00:00Z",
                "html_url": "https://github.com/example/project/issues/456",
            },
            fetched_at=utc_now(),
        )
    )

    assert item["url"] == "https://github.com/example/project/issues/456"
