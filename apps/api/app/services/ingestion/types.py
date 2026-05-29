from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class RawFetchedItem:
    source: str
    external_id: str
    raw_json: dict[str, Any]
    fetched_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)

