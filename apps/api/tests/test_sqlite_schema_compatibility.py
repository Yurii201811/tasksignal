import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.db.session import ensure_sqlite_schema_compatibility


def test_sqlite_schema_compatibility_adds_missing_local_columns(tmp_path) -> None:
    stale_db = tmp_path / "stale_tasksignal.db"
    engine = create_engine(f"sqlite:///{stale_db}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE scan_jobs (id TEXT PRIMARY KEY)"))
        connection.execute(text("INSERT INTO scan_jobs (id) VALUES ('scan-1')"))
        connection.execute(text("CREATE TABLE research_projects (id TEXT PRIMARY KEY)"))
        connection.execute(text("INSERT INTO research_projects (id) VALUES ('project-1')"))
        connection.execute(text("CREATE TABLE opportunities (id TEXT PRIMARY KEY)"))
        connection.execute(text("INSERT INTO opportunities (id) VALUES ('opportunity-1')"))

    ensure_sqlite_schema_compatibility(engine)

    inspector = inspect(engine)
    scan_columns = {column["name"] for column in inspector.get_columns("scan_jobs")}
    project_columns = {column["name"] for column in inspector.get_columns("research_projects")}
    assert {
        "signals_detected",
        "clusters_created",
        "opportunities_created",
        "outcome_message",
    }.issubset(scan_columns)
    assert {
        "schedule_interval_hours",
        "last_run_at",
        "next_run_at",
        "run_count",
    }.issubset(project_columns)
    opportunity_columns = {column["name"] for column in inspector.get_columns("opportunities")}
    assert {"review_state", "review_note", "decision_updated_at"}.issubset(opportunity_columns)
    opportunity_indexes = {index["name"] for index in inspector.get_indexes("opportunities")}
    assert "ix_opportunities_review_state" in opportunity_indexes

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT signals_detected, clusters_created, opportunities_created "
                "FROM scan_jobs WHERE id = 'scan-1'"
            )
        ).one()
    assert row == (0, 0, 0)

    with engine.connect() as connection:
        opportunity_row = connection.execute(
            text(
                "SELECT review_state, review_note, decision_updated_at "
                "FROM opportunities WHERE id = 'opportunity-1'"
            )
        ).one()
    assert opportunity_row == ("new", None, None)


ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "apps" / "api"


def run_alembic(database_url: str, *args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
    )


def test_decision_migration_preserves_existing_opportunity(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    run_alembic(database_url, "upgrade", "0005_scan_outcomes")
    migration_engine = create_engine(database_url)
    now = "2026-07-09T12:00:00+00:00"
    cluster_id = "11111111111111111111111111111111"
    opportunity_id = "22222222222222222222222222222222"
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO clusters "
                "(id, title, summary, centroid_embedding, size, created_at, updated_at) "
                "VALUES (:id, :title, :summary, NULL, 1, :created_at, :updated_at)"
            ),
            {
                "id": cluster_id,
                "title": "Existing cluster",
                "summary": "Existing summary",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO opportunities "
                "(id, cluster_id, title, problem_statement, target_user, "
                "current_workaround, suggested_mvp, why_now, feasibility_score, "
                "opportunity_score, competition_notes, scoring_breakdown_json, "
                "generated_prompt, created_at, updated_at) VALUES "
                "(:id, :cluster_id, :title, :problem, :target, :workaround, :mvp, "
                ":why_now, 0.8, 0.7, :competition, :breakdown, :prompt, "
                ":created_at, :updated_at)"
            ),
            {
                "id": opportunity_id,
                "cluster_id": cluster_id,
                "title": "Existing decision candidate",
                "problem": "Existing problem",
                "target": "Maintainers",
                "workaround": "Manual review",
                "mvp": "Decision queue",
                "why_now": "Evidence exists",
                "competition": "Narrow scope",
                "breakdown": "{}",
                "prompt": "# Build existing candidate",
                "created_at": now,
                "updated_at": now,
            },
        )
    migration_engine.dispose()

    run_alembic(database_url, "upgrade", "head")
    upgraded_engine = create_engine(database_url)
    with upgraded_engine.connect() as connection:
        upgraded = connection.execute(
            text(
                "SELECT review_state, review_note, decision_updated_at, title "
                "FROM opportunities WHERE id = :id"
            ),
            {"id": opportunity_id},
        ).one()
    assert upgraded == ("new", None, None, "Existing decision candidate")
    upgraded_engine.dispose()

    run_alembic(database_url, "downgrade", "0005_scan_outcomes")
    downgraded_engine = create_engine(database_url)
    columns = {column["name"] for column in inspect(downgraded_engine).get_columns("opportunities")}
    assert "review_state" not in columns
    with downgraded_engine.connect() as connection:
        title = connection.scalar(
            text("SELECT title FROM opportunities WHERE id = :id"),
            {"id": opportunity_id},
        )
    assert title == "Existing decision candidate"
    downgraded_engine.dispose()
