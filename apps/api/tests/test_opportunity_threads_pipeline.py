from sqlalchemy import func, select

from app.models.all_models import Opportunity, OpportunityThread, ResearchProject
from app.services.ingestion.connectors import BaseConnector
from app.services.ingestion.types import RawFetchedItem, utc_now
from app.workers.scan_pipeline import process_scan


def signal_item(external_id: str) -> RawFetchedItem:
    return RawFetchedItem(
        source="mock",
        external_id=external_id,
        raw_json={
            "title": f"GitHub Actions workflow debugging is painful #{external_id}",
            "body": (
                "Developers manually copy paste CI failures every week. It takes forever "
                "and teams would pay for a focused workflow dashboard."
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


def project(db_session, name: str) -> ResearchProject:
    value = ResearchProject(
        name=name,
        source_type="mock",
        query="ci pain",
        limit=10,
        cadence="manual",
        labels_json=[],
    )
    db_session.add(value)
    db_session.commit()
    db_session.refresh(value)
    return value


def run(db_session, research_project, items):
    return process_scan(
        db_session,
        source=research_project.source_type if research_project else "mock",
        query=research_project.query if research_project else "ci pain",
        limit=10,
        connector=StaticConnector(items),
        research_project=research_project,
    )


def test_identical_project_runs_attach_snapshots_to_one_exact_thread(db_session) -> None:
    research_project = project(db_session, "First")
    items = [signal_item("a"), signal_item("b")]

    first_scan = run(db_session, research_project, items)
    second_scan = run(db_session, research_project, items)

    assert first_scan.status == second_scan.status == "completed"
    threads = db_session.scalars(select(OpportunityThread)).all()
    snapshots = db_session.scalars(
        select(Opportunity).order_by(Opportunity.created_at, Opportunity.id)
    ).all()
    assert len(threads) == 1
    assert len(snapshots) == 2
    assert {snapshot.thread_id for snapshot in snapshots} == {threads[0].id}
    assert snapshots[0].match_method == "new_no_candidates"
    assert snapshots[1].match_method == "exact_evidence"
    assert snapshots[1].match_confidence == 1.0
    assert snapshots[0].evidence_hash == snapshots[1].evidence_hash
    assert threads[0].project_id == research_project.id
    assert threads[0].current_snapshot_id == snapshots[1].id


def test_matching_never_crosses_project_boundaries(db_session) -> None:
    first_project = project(db_session, "First")
    second_project = project(db_session, "Second")
    items = [signal_item("same-a"), signal_item("same-b")]

    run(db_session, first_project, items)
    run(db_session, second_project, items)

    threads = db_session.scalars(select(OpportunityThread)).all()
    snapshots = db_session.scalars(select(Opportunity)).all()
    assert len(threads) == 2
    assert len({snapshot.thread_id for snapshot in snapshots}) == 2
    assert {thread.project_id for thread in threads} == {
        first_project.id,
        second_project.id,
    }


def test_untracked_manual_scans_always_create_one_to_one_threads(db_session) -> None:
    items = [signal_item("manual-a"), signal_item("manual-b")]

    run(db_session, None, items)
    run(db_session, None, items)

    assert db_session.scalar(select(func.count()).select_from(Opportunity)) == 2
    assert db_session.scalar(select(func.count()).select_from(OpportunityThread)) == 2
    threads = db_session.scalars(select(OpportunityThread)).all()
    snapshots = db_session.scalars(select(Opportunity)).all()
    assert {thread.lineage_status for thread in threads} == {"untracked"}
    assert {thread.project_id for thread in threads} == {None}
    assert {snapshot.match_method for snapshot in snapshots} == {"new_untracked"}
    assert all(len(snapshot.evidence_hash) == 64 for snapshot in snapshots)
    assert all(len(snapshot.content_hash) == 64 for snapshot in snapshots)
