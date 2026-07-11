from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.all_models import ResearchProject, ScanJob
from app.workers.scan_pipeline import ProjectVersionConflict, reserve_scan_job


def test_project_mutations_advance_version_and_stale_run_reserves_nothing(client) -> None:
    created = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Versioned research",
            "source_type": "fixture",
            "query": "workflow",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    assert created.status_code == 200
    project = created.json()
    assert project["version"] == 1

    updated = client.patch(
        f"/api/v1/research-projects/{project['id']}",
        json={"name": "Versioned research updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    run = client.post(f"/api/v1/research-projects/{project['id']}/run")
    assert run.status_code == 200
    current = client.get(f"/api/v1/research-projects/{project['id']}").json()
    assert current["version"] == 3

    with Session(engine) as db:
        project_row = db.get(ResearchProject, UUID(project["id"]))
        assert project_row is not None
        scan_count = db.scalar(select(func.count()).select_from(ScanJob))
        with pytest.raises(ProjectVersionConflict, match="expected 2, current 3"):
            reserve_scan_job(
                db,
                source_type="fixture",
                query=project_row.query,
                requested_limit=project_row.limit,
                research_project_id=project_row.id,
                expected_project_version=2,
            )
        db.rollback()
        assert db.scalar(select(func.count()).select_from(ScanJob)) == scan_count


def test_concurrent_project_updates_with_one_expected_version_commit_once(client) -> None:
    project = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Concurrent version",
            "source_type": "fixture",
            "query": "workflow",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    ).json()

    def update(name: str):
        return client.patch(
            f"/api/v1/research-projects/{project['id']}",
            json={"name": name, "expected_version": project["version"]},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(update, ["First winner", "Second winner"]))

    assert sorted(response.status_code for response in responses) == [200, 409]
    saved = client.get(f"/api/v1/research-projects/{project['id']}").json()
    assert saved["version"] == 2
    assert saved["name"] in {"First winner", "Second winner"}
