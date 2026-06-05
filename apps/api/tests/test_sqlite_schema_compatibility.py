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

    ensure_sqlite_schema_compatibility(engine)

    inspector = inspect(engine)
    scan_columns = {column["name"] for column in inspector.get_columns("scan_jobs")}
    project_columns = {
        column["name"] for column in inspector.get_columns("research_projects")
    }
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

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT signals_detected, clusters_created, opportunities_created "
                "FROM scan_jobs WHERE id = 'scan-1'"
            )
        ).one()
    assert row == (0, 0, 0)
