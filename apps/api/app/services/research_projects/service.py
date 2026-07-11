from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import ResearchProject, ResearchProjectRun

CADENCE_INTERVAL_HOURS = {
    "manual": None,
    "hourly": 1,
    "daily": 24,
    "weekly": 24 * 7,
}


def interval_hours_for_project(
    cadence: str,
    explicit_interval: int | None,
) -> int | None:
    if explicit_interval:
        return max(1, min(24 * 31, explicit_interval))
    return CADENCE_INTERVAL_HOURS.get(cadence.strip().lower())


def next_run_at_from(
    start: datetime,
    cadence: str,
    explicit_interval: int | None,
) -> datetime | None:
    interval = interval_hours_for_project(cadence, explicit_interval)
    if interval is None:
        return None
    return start + timedelta(hours=interval)


def mark_latest_project_run(
    db: Session,
    *,
    project_id: UUID,
    run_sequence: int,
    scan_id: UUID,
    finished_at: datetime,
) -> None:
    latest_sequence = db.scalar(
        select(func.max(ResearchProjectRun.sequence)).where(
            ResearchProjectRun.project_id == project_id
        )
    )
    if latest_sequence != run_sequence:
        return

    project = db.scalar(
        select(ResearchProject)
        .where(ResearchProject.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if project is None:
        return
    project.last_scan_id = scan_id
    project.last_run_at = finished_at
    project.next_run_at = next_run_at_from(
        finished_at,
        project.cadence,
        project.schedule_interval_hours,
    )
    project.updated_at = finished_at
