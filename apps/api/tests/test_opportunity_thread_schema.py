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


def test_models_expose_opportunity_thread_schema() -> None:
    tables = Base.metadata.tables
    assert "opportunity_threads" in tables
    assert "opportunity_decision_events" in tables
    assert {
        "id",
        "project_id",
        "current_snapshot_id",
        "lineage_status",
        "review_state",
        "review_note",
        "decision_updated_at",
        "version",
        "created_at",
        "updated_at",
    } == set(tables["opportunity_threads"].columns.keys())
    assert {
        "thread_id",
        "run_id",
        "evidence_hash",
        "content_hash",
        "match_method",
        "match_confidence",
        "match_margin",
        "centroid_similarity",
        "evidence_jaccard",
        "title_jaccard",
        "embedding_model",
        "embedding_backend",
    }.issubset(tables["opportunities"].columns.keys())


def test_opportunity_thread_migration_backfills_legacy_decisions_without_lineage_guessing(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'opportunity-threads.db'}"
    run_alembic(database_url, "upgrade", "0007_research_memory")
    engine = create_engine(database_url)
    now = "2026-07-11T12:00:00+00:00"
    cluster_id = "11111111111111111111111111111111"
    opportunity_id = "22222222222222222222222222222222"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO clusters "
                "(id, scan_id, title, summary, centroid_embedding, size, created_at, updated_at) "
                "VALUES (:id, NULL, 'Legacy cluster', 'Legacy summary', NULL, 1, :now, :now)"
            ),
            {"id": cluster_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO opportunities "
                "(id, scan_id, cluster_id, title, problem_statement, target_user, "
                "current_workaround, suggested_mvp, why_now, feasibility_score, "
                "opportunity_score, competition_notes, scoring_breakdown_json, "
                "generated_prompt, review_state, review_note, decision_updated_at, "
                "created_at, updated_at) VALUES "
                "(:id, NULL, :cluster_id, 'Legacy opportunity', 'Problem', 'Builder', "
                "'Manual', 'MVP', 'Now', 0.8, 0.7, 'Narrow', '{}', '# Build', "
                "'promising', 'Keep this local note.', :now, :now, :now)"
            ),
            {"id": opportunity_id, "cluster_id": cluster_id, "now": now},
        )
    engine.dispose()

    run_alembic(database_url, "upgrade", "head")
    upgraded = create_engine(database_url)
    inspector = inspect(upgraded)
    assert {"opportunity_threads", "opportunity_decision_events"}.issubset(
        inspector.get_table_names()
    )
    opportunity_columns = {
        column["name"] for column in inspector.get_columns("opportunities")
    }
    assert {"thread_id", "evidence_hash", "content_hash", "match_method"}.issubset(
        opportunity_columns
    )
    with upgraded.connect() as connection:
        row = connection.execute(
            text(
                "SELECT o.thread_id, o.evidence_hash, o.content_hash, o.match_method, "
                "t.project_id, t.current_snapshot_id, t.lineage_status, t.review_state, "
                "t.review_note, t.version "
                "FROM opportunities o JOIN opportunity_threads t ON t.id = o.thread_id "
                "WHERE o.id = :id"
            ),
            {"id": opportunity_id},
        ).one()
        event = connection.execute(
            text(
                "SELECT event_type, actor_type, snapshot_id, next_state, next_note "
                "FROM opportunity_decision_events WHERE thread_id = :thread_id"
            ),
            {"thread_id": row.thread_id},
        ).one()
    assert row.project_id is None
    assert row.current_snapshot_id == opportunity_id
    assert row.lineage_status == "untracked"
    assert row.review_state == "promising"
    assert row.review_note == "Keep this local note."
    assert row.version == 1
    assert row.match_method == "legacy_backfill"
    assert len(row.evidence_hash) == len(row.content_hash) == 64
    assert event == (
        "legacy_backfill",
        "system",
        opportunity_id,
        "promising",
        "Keep this local note.",
    )
    upgraded.dispose()

    run_alembic(database_url, "downgrade", "0007_research_memory")
    downgraded = create_engine(database_url)
    downgraded_inspector = inspect(downgraded)
    assert "opportunity_threads" not in downgraded_inspector.get_table_names()
    assert "opportunity_decision_events" not in downgraded_inspector.get_table_names()
    assert "thread_id" not in {
        column["name"] for column in downgraded_inspector.get_columns("opportunities")
    }
    with downgraded.connect() as connection:
        preserved = connection.execute(
            text(
                "SELECT review_state, review_note FROM opportunities WHERE id = :id"
            ),
            {"id": opportunity_id},
        ).one()
    assert preserved == ("promising", "Keep this local note.")
    downgraded.dispose()


def test_opportunity_thread_backfill_uses_only_exact_complete_run_lineage(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'tracked-opportunity.db'}"
    run_alembic(database_url, "upgrade", "0007_research_memory")
    engine = create_engine(database_url)
    now = "2026-07-11T12:00:00+00:00"
    ids = {
        "source": "10000000000000000000000000000000",
        "scan": "20000000000000000000000000000000",
        "project": "30000000000000000000000000000000",
        "run": "40000000000000000000000000000000",
        "cluster": "50000000000000000000000000000000",
        "opportunity": "60000000000000000000000000000000",
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources (id, name, type, config_json, enabled, created_at) "
                "VALUES (:id, 'Mock', 'mock', '{}', 1, :now)"
            ),
            {"id": ids["source"], "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO scan_jobs "
                "(id, source_id, status, query, started_at, finished_at, error_message, "
                "items_found, items_saved, signals_detected, clusters_created, "
                "opportunities_created, outcome_message) VALUES "
                "(:id, :source, 'completed', 'ci', :now, :now, NULL, 2, 2, 2, 1, 1, 'ok')"
            ),
            {"id": ids["scan"], "source": ids["source"], "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO research_projects "
                "(id, name, description, source_type, query, \"limit\", cadence, labels_json, "
                "enabled, last_scan_id, created_at, updated_at, schedule_interval_hours, "
                "last_run_at, next_run_at, run_count) VALUES "
                "(:id, 'Tracked', NULL, 'mock', 'ci', 10, 'manual', '[]', 1, :scan, "
                ":now, :now, NULL, :now, NULL, 1)"
            ),
            {"id": ids["project"], "scan": ids["scan"], "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO research_project_runs "
                "(id, project_id, scan_id, sequence, source_type, query, requested_limit, "
                "lineage_complete, created_at) VALUES "
                "(:id, :project, :scan, 1, 'mock', 'ci', 10, 1, :now)"
            ),
            {
                "id": ids["run"],
                "project": ids["project"],
                "scan": ids["scan"],
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO clusters "
                "(id, scan_id, title, summary, centroid_embedding, size, created_at, updated_at) "
                "VALUES (:id, :scan, 'Tracked cluster', 'Summary', NULL, 1, :now, :now)"
            ),
            {"id": ids["cluster"], "scan": ids["scan"], "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO opportunities "
                "(id, scan_id, cluster_id, title, problem_statement, target_user, "
                "current_workaround, suggested_mvp, why_now, feasibility_score, "
                "opportunity_score, competition_notes, scoring_breakdown_json, "
                "generated_prompt, review_state, review_note, decision_updated_at, "
                "created_at, updated_at) VALUES "
                "(:id, :scan, :cluster, 'Tracked opportunity', 'Problem', 'Builder', "
                "'Manual', 'MVP', 'Now', 0.8, 0.7, 'Narrow', '{}', '# Build', "
                "'new', NULL, NULL, :now, :now)"
            ),
            {
                "id": ids["opportunity"],
                "scan": ids["scan"],
                "cluster": ids["cluster"],
                "now": now,
            },
        )
    engine.dispose()

    run_alembic(database_url, "upgrade", "head")
    upgraded = create_engine(database_url)
    with upgraded.connect() as connection:
        row = connection.execute(
            text(
                "SELECT t.project_id, t.lineage_status, o.run_id "
                "FROM opportunities o JOIN opportunity_threads t ON t.id = o.thread_id "
                "WHERE o.id = :id"
            ),
            {"id": ids["opportunity"]},
        ).one()
    assert row == (ids["project"], "complete", ids["run"])
    upgraded.dispose()
