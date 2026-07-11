from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class RawFetchedItem:
    source: str
    external_id: str
    raw_json: dict[str, Any]
    fetched_at: datetime


@dataclass(frozen=True)
class ConnectorFailure:
    """Sanitized connector failure metadata suitable for runtime recording."""

    category: str
    message: str
    status_code: int | None = None
    retry_after_seconds: int | None = None
    retriable: bool = False


@dataclass(frozen=True)
class ConnectorFetchResult:
    """Items plus bounded, non-sensitive connector runtime metadata."""

    items: list[RawFetchedItem]
    requests_made: int
    retry_after_seconds: int | None
    last_success_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
