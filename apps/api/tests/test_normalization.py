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

