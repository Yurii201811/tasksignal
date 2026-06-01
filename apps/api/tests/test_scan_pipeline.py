from __future__ import annotations

from sqlalchemy import select

from app.models.all_models import NormalizedItem, Opportunity, RawItem
from app.services.ingestion.connectors import BaseConnector
from app.services.ingestion.types import RawFetchedItem, utc_now
from app.workers import scan_pipeline
from app.workers.scan_pipeline import process_scan


def live_signal_item(
    external_id: str,
    author: str = "raw-user",
    unique_text: bool = True,
) -> RawFetchedItem:
    suffix = f" #{external_id}" if unique_text else ""
    return RawFetchedItem(
        source="mock",
        external_id=external_id,
        raw_json={
            "title": f"GitHub Actions workflow debugging is painful{suffix}",
            "body": (
                "Every week developers manually copy paste GitHub Actions logs "
                "and YAML failures into a spreadsheet. It takes forever and teams "
                "would pay for a dashboard."
            ),
            "author": author,
            "created_at": "2026-05-20T00:00:00Z",
            "url": f"https://example.test/items/{external_id}",
            "tags": ["ci"],
        },
        fetched_at=utc_now(),
    )


class MockConnector(BaseConnector):
    name = "mock"

    def __init__(self, items: list[RawFetchedItem]) -> None:
        self.items = items

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        return self.items[:limit]


class FailingConnector(BaseConnector):
    name = "failing"

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        raise RuntimeError("Live API unavailable")


def test_scan_job_success_path_with_mocked_connector(db_session) -> None:
    job = process_scan(
        db_session,
        source="mock",
        query="github actions",
        limit=3,
        connector=MockConnector([live_signal_item(str(index)) for index in range(3)]),
    )

    assert job.status == "completed"
    assert job.items_found == 3
    assert job.items_saved == 3
    assert job.finished_at is not None
    assert job.error_message is None
    assert len(db_session.scalars(select(Opportunity.id)).all()) == 1

    raw_item = db_session.scalar(select(RawItem).where(RawItem.external_id == "0"))
    assert raw_item is not None
    assert "author" not in raw_item.raw_json


def test_scan_job_creates_live_opportunity_from_small_signal_set(db_session) -> None:
    job = process_scan(
        db_session,
        source="mock",
        query="github actions",
        limit=2,
        connector=MockConnector([live_signal_item(str(index)) for index in range(2)]),
    )

    assert job.status == "completed"
    assert job.items_found == 2
    assert job.items_saved == 2

    opportunities = db_session.scalars(select(Opportunity)).all()
    assert len(opportunities) == 1
    assert opportunities[0].generated_prompt
    assert "Top source excerpts" in opportunities[0].generated_prompt


def test_scan_job_failure_path(db_session) -> None:
    job = process_scan(
        db_session,
        source="mock",
        query="github actions",
        limit=3,
        connector=FailingConnector(),
    )

    assert job.status == "failed"
    assert job.items_found == 0
    assert job.items_saved == 0
    assert job.finished_at is not None
    assert job.error_message is not None
    assert "Live API unavailable" in job.error_message


def test_scan_deduplicates_normalized_items(db_session) -> None:
    first = live_signal_item("duplicate-a", unique_text=False)
    second = live_signal_item("duplicate-b", unique_text=False)
    job = process_scan(
        db_session,
        source="mock",
        query="github actions",
        limit=2,
        connector=MockConnector([first, second]),
    )

    assert job.status == "completed"
    assert job.items_found == 2
    assert job.items_saved == 1
    assert len(db_session.scalars(select(NormalizedItem.id)).all()) == 1


def test_scan_api_route_runs_pipeline_with_request_payload(client, monkeypatch) -> None:
    monkeypatch.setitem(
        scan_pipeline.CONNECTOR_FACTORIES,
        "mockapi",
        lambda: MockConnector(
            [
                RawFetchedItem(
                    source="mockapi",
                    external_id=str(index),
                    raw_json=live_signal_item(str(index)).raw_json,
                    fetched_at=utc_now(),
                )
                for index in range(3)
            ]
        ),
    )

    response = client.post(
        "/api/scans",
        json={"source": "mockapi", "query": "github actions", "limit": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["source_type"] == "mockapi"
    assert payload["items_found"] == 3
    assert payload["items_saved"] == 3

    scans = client.get("/api/scans").json()
    assert len(scans) == 1
    assert scans[0]["status"] == "completed"
    assert client.get("/api/opportunities").json()


def test_scan_api_route_rejects_unsupported_source(client) -> None:
    response = client.post(
        "/api/scans",
        json={"source": "unsupported", "query": "anything", "limit": 3},
    )

    assert response.status_code == 400
    assert "Unsupported source" in response.json()["detail"]
    assert client.get("/api/scans").json() == []
    assert client.get("/api/stats").json()["total_items"] == 0
