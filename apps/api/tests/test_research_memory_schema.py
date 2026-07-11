import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.db.base import Base
from app.models import all_models  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "apps" / "api"


def run_alembic(database_url: str, *args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
    )


def test_models_expose_research_memory_schema() -> None:
    tables = Base.metadata.tables
    assert "research_project_runs" in tables
    assert "scan_items" in tables

    run_columns = set(tables["research_project_runs"].columns.keys())
    assert run_columns == {
        "id",
        "project_id",
        "scan_id",
        "sequence",
        "source_type",
        "query",
        "requested_limit",
        "source_origin",
        "lineage_complete",
        "created_at",
    }
    assert set(tables["scan_items"].primary_key.columns.keys()) == {"scan_id", "item_id"}
    assert "scan_id" in tables["clusters"].columns
    assert "scan_id" in tables["opportunities"].columns


def test_research_memory_migration_preserves_legacy_snapshots(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'research-memory.db'}"
    run_alembic(database_url, "upgrade", "0006_decision_workbench")
    migration_engine = create_engine(database_url)
    now = "2026-07-11T12:00:00+00:00"
    cluster_id = "11111111111111111111111111111111"
    opportunity_id = "22222222222222222222222222222222"
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO clusters "
                "(id, title, summary, centroid_embedding, size, created_at, updated_at) "
                "VALUES (:id, 'Legacy cluster', 'Legacy summary', NULL, 1, :now, :now)"
            ),
            {"id": cluster_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO opportunities "
                "(id, cluster_id, title, problem_statement, target_user, current_workaround, "
                "suggested_mvp, why_now, feasibility_score, opportunity_score, "
                "competition_notes, scoring_breakdown_json, generated_prompt, "
                "review_state, created_at, updated_at) VALUES "
                "(:id, :cluster_id, 'Legacy opportunity', 'Problem', 'Builder', 'Manual', "
                "'MVP', 'Now', 0.8, 0.7, 'Narrow', '{}', '# Build', 'promising', :now, :now)"
            ),
            {"id": opportunity_id, "cluster_id": cluster_id, "now": now},
        )
    migration_engine.dispose()

    run_alembic(database_url, "upgrade", "head")
    upgraded_engine = create_engine(database_url)
    inspector = inspect(upgraded_engine)
    assert {"research_project_runs", "scan_items"}.issubset(inspector.get_table_names())
    assert "scan_id" in {column["name"] for column in inspector.get_columns("clusters")}
    assert "scan_id" in {column["name"] for column in inspector.get_columns("opportunities")}
    with upgraded_engine.connect() as connection:
        preserved = connection.execute(
            text(
                "SELECT c.scan_id, o.scan_id, o.review_state "
                "FROM clusters c JOIN opportunities o ON o.cluster_id = c.id "
                "WHERE o.id = :id"
            ),
            {"id": opportunity_id},
        ).one()
    assert preserved == (None, None, "promising")
    upgraded_engine.dispose()

    run_alembic(database_url, "downgrade", "0006_decision_workbench")
    downgraded_engine = create_engine(database_url)
    downgraded_inspector = inspect(downgraded_engine)
    assert "research_project_runs" not in downgraded_inspector.get_table_names()
    assert "scan_items" not in downgraded_inspector.get_table_names()
    assert "scan_id" not in {
        column["name"] for column in downgraded_inspector.get_columns("clusters")
    }
    assert "scan_id" not in {
        column["name"] for column in downgraded_inspector.get_columns("opportunities")
    }
    downgraded_engine.dispose()
