from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import (
    Cluster,
    ItemEmbedding,
    ItemSignal,
    NormalizedItem,
    Opportunity,
    ResearchProject,
    ResearchProjectRun,
    ScanItem,
)
from app.services.ingestion.connectors import BaseConnector
from app.services.ingestion.types import RawFetchedItem, utc_now
from app.workers import scan_pipeline
from app.workers.scan_pipeline import process_scan


def signal_item(external_id: str, *, unique_text: bool = True) -> RawFetchedItem:
    suffix = f" #{external_id}" if unique_text else ""
    return RawFetchedItem(
        source="mock",
        external_id=external_id,
        raw_json={
            "title": f"GitHub Actions workflow debugging is painful{suffix}",
            "body": (
                "Developers manually copy paste CI logs and YAML failures every week. "
                "It takes forever and teams would pay for a focused dashboard."
            ),
            "created_at": "2026-07-11T00:00:00Z",
            "url": f"https://example.test/items/{external_id}",
            "tags": ["ci"],
        },
        fetched_at=utc_now(),
    )


class StaticConnector(BaseConnector):
    name = "mock"

    def __init__(self, items: list[RawFetchedItem]) -> None:
        self.items = items

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        return self.items[:limit]


class FailingConnector(BaseConnector):
    name = "mock"

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        raise RuntimeError("fixture source unavailable")


def create_project(db_session) -> ResearchProject:
    project = ResearchProject(
        name="CI pain research",
        source_type="mock",
        query="github actions",
        limit=3,
        cadence="manual",
        labels_json=["ci"],
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def test_project_runs_snapshot_inputs_and_record_every_observed_item(db_session) -> None:
    project = create_project(db_session)
    items = [signal_item(str(index)) for index in range(3)]

    scan = process_scan(
        db_session,
        source=project.source_type,
        query=project.query,
        limit=project.limit,
        connector=StaticConnector(items),
        research_project=project,
    )

    run = db_session.scalar(
        select(ResearchProjectRun).where(ResearchProjectRun.scan_id == scan.id)
    )
    assert run is not None
    assert run.project_id == project.id
    assert run.sequence == 1
    assert run.source_type == "mock"
    assert run.query == "github actions"
    assert run.requested_limit == 3
    assert run.lineage_complete is True

    observations = db_session.scalars(
        select(ScanItem).where(ScanItem.scan_id == scan.id)
    ).all()
    assert len(observations) == 3
    assert all(observation.created_in_scan for observation in observations)
    assert set(db_session.scalars(select(Cluster.scan_id)).all()) == {scan.id}
    assert set(db_session.scalars(select(Opportunity.scan_id)).all()) == {scan.id}


def test_identical_project_run_reuses_derived_evidence_but_clusters_all_observations(
    db_session,
    monkeypatch,
) -> None:
    project = create_project(db_session)
    items = [signal_item(str(index)) for index in range(3)]

    detector_calls = 0
    embedded_text_count = 0
    original_detector = scan_pipeline.detect_problem_signal
    original_embed_texts = scan_pipeline.EmbeddingService.embed_texts

    def recording_detector(title: str, body: str):
        nonlocal detector_calls
        detector_calls += 1
        return original_detector(title, body)

    def recording_embed_texts(service, texts: list[str]):
        nonlocal embedded_text_count
        embedded_text_count += len(texts)
        return original_embed_texts(service, texts)

    monkeypatch.setattr(scan_pipeline, "detect_problem_signal", recording_detector)
    monkeypatch.setattr(
        scan_pipeline.EmbeddingService,
        "embed_texts",
        recording_embed_texts,
    )

    first = process_scan(
        db_session,
        source=project.source_type,
        query=project.query,
        limit=project.limit,
        connector=StaticConnector(items),
        research_project=project,
    )
    second = process_scan(
        db_session,
        source=project.source_type,
        query=project.query,
        limit=project.limit,
        connector=StaticConnector(items),
        research_project=project,
    )

    assert first.items_saved == 3
    assert second.items_saved == 0
    assert second.signals_detected == 3
    assert second.clusters_created == 1
    assert second.opportunities_created == 1
    assert db_session.scalar(select(func.count()).select_from(NormalizedItem)) == 3
    assert db_session.scalar(select(func.count()).select_from(ItemSignal)) == 3
    assert db_session.scalar(select(func.count()).select_from(ItemEmbedding)) == 3
    assert db_session.scalar(select(func.count()).select_from(Cluster)) == 2
    assert db_session.scalar(select(func.count()).select_from(Opportunity)) == 2
    assert detector_calls == 3
    assert embedded_text_count == 3

    runs = db_session.scalars(
        select(ResearchProjectRun)
        .where(ResearchProjectRun.project_id == project.id)
        .order_by(ResearchProjectRun.sequence)
    ).all()
    assert [run.sequence for run in runs] == [1, 2]
    second_observations = db_session.scalars(
        select(ScanItem).where(ScanItem.scan_id == second.id)
    ).all()
    assert len(second_observations) == 3
    assert not any(observation.created_in_scan for observation in second_observations)


def test_partially_new_run_marks_observation_provenance(db_session) -> None:
    project = create_project(db_session)
    previously_seen = signal_item("seen")
    process_scan(
        db_session,
        source=project.source_type,
        query=project.query,
        limit=project.limit,
        connector=StaticConnector([previously_seen]),
        research_project=project,
    )

    second = process_scan(
        db_session,
        source=project.source_type,
        query=project.query,
        limit=project.limit,
        connector=StaticConnector([previously_seen, signal_item("new")]),
        research_project=project,
    )

    flags = db_session.execute(
        select(NormalizedItem.external_id, ScanItem.created_in_scan)
        .join(ScanItem, ScanItem.item_id == NormalizedItem.id)
        .where(ScanItem.scan_id == second.id)
        .order_by(NormalizedItem.external_id)
    ).all()
    assert flags == [("new", True), ("seen", False)]
    assert second.items_saved == 1
    assert second.signals_detected == 2


def test_zero_and_failed_project_runs_remain_auditable(db_session) -> None:
    project = create_project(db_session)

    empty_scan = process_scan(
        db_session,
        source=project.source_type,
        query=project.query,
        limit=project.limit,
        connector=StaticConnector([]),
        research_project=project,
    )
    failed_scan = process_scan(
        db_session,
        source=project.source_type,
        query=project.query,
        limit=project.limit,
        connector=FailingConnector(),
        research_project=project,
    )

    empty_run = db_session.scalar(
        select(ResearchProjectRun).where(ResearchProjectRun.scan_id == empty_scan.id)
    )
    failed_run = db_session.scalar(
        select(ResearchProjectRun).where(ResearchProjectRun.scan_id == failed_scan.id)
    )
    assert empty_scan.status == "completed"
    assert empty_run is not None and empty_run.lineage_complete is True
    assert failed_scan.status == "failed"
    assert failed_run is not None and failed_run.lineage_complete is False
    assert db_session.scalar(
        select(func.count()).select_from(ScanItem).where(ScanItem.scan_id == failed_scan.id)
    ) == 0
    assert [empty_run.sequence, failed_run.sequence] == [1, 2]


def test_late_pipeline_failure_rolls_back_partial_lineage(db_session, monkeypatch) -> None:
    project = create_project(db_session)

    def fail_generation(*_args, **_kwargs):
        raise RuntimeError("generation failed after evidence processing")

    monkeypatch.setattr(scan_pipeline, "generate_opportunity", fail_generation)
    scan = process_scan(
        db_session,
        source=project.source_type,
        query=project.query,
        limit=project.limit,
        connector=StaticConnector(
            [signal_item("late-failure-a"), signal_item("late-failure-b")]
        ),
        research_project=project,
    )

    run = db_session.scalar(
        select(ResearchProjectRun).where(ResearchProjectRun.scan_id == scan.id)
    )
    assert scan.status == "failed"
    assert run is not None and run.lineage_complete is False
    assert db_session.scalar(select(func.count()).select_from(ScanItem)) == 0
    assert db_session.scalar(select(func.count()).select_from(NormalizedItem)) == 0
    assert db_session.scalar(select(func.count()).select_from(Cluster)) == 0
    assert db_session.scalar(select(func.count()).select_from(Opportunity)) == 0


def test_concurrent_local_project_runs_receive_unique_complete_sequences(db_session) -> None:
    project = create_project(db_session)
    project_id = project.id
    bind = db_session.get_bind()
    db_session.close()

    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)

    def run_once() -> str:
        with Session(bind) as session:
            local_project = session.get(ResearchProject, project_id)
            assert local_project is not None
            barrier.wait()
            scan = process_scan(
                session,
                source=local_project.source_type,
                query=local_project.query,
                limit=local_project.limit,
                connector=StaticConnector([signal_item("shared")]),
                research_project=local_project,
            )
            return scan.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _index: run_once(), range(2)))

    with Session(bind) as session:
        runs = session.scalars(
            select(ResearchProjectRun)
            .where(ResearchProjectRun.project_id == project_id)
            .order_by(ResearchProjectRun.sequence)
        ).all()
        assert statuses == ["completed", "completed"]
        assert [run.sequence for run in runs] == [1, 2]
        assert all(run.lineage_complete for run in runs)
        assert session.scalar(select(func.count()).select_from(ScanItem)) == 2
        assert session.scalar(select(func.count()).select_from(NormalizedItem)) == 1
        assert session.scalar(select(func.count()).select_from(ItemSignal)) == 1
        assert session.scalar(select(func.count()).select_from(ItemEmbedding)) == 1
