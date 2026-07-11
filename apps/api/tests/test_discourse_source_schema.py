import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

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


def test_models_expose_discourse_source_state_and_project_run_linkage() -> None:
    tables = Base.metadata.tables
    assert "discourse_source_state" in tables
    assert set(tables["discourse_source_state"].columns.keys()) == {
        "source_id",
        "scheme",
        "host",
        "port",
        "authorized_at",
        "terms_confirmed_at",
        "last_success_at",
        "last_failure_at",
        "last_failure_code",
        "last_failure_message",
        "last_http_status",
        "retry_after_at",
        "created_at",
        "updated_at",
    }
    assert "source_id" in tables["research_projects"].columns
    assert "source_origin" in tables["research_project_runs"].columns
    assert {
        "observed_source",
        "observed_external_id",
        "observed_url",
    }.issubset(tables["scan_items"].columns.keys())


def test_discourse_source_migration_preserves_legacy_projects_and_downgrades(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'discourse-source-state.db'}"
    run_alembic(database_url, "upgrade", "0007_opportunity_threads")
    engine = create_engine(database_url)
    source_id = "10000000000000000000000000000000"
    project_id = "20000000000000000000000000000000"
    scan_id = "30000000000000000000000000000000"
    item_id = "40000000000000000000000000000000"
    now = "2026-07-11T12:00:00+00:00"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources (id, name, type, config_json, enabled, created_at) "
                "VALUES (:id, 'Hacker News', 'hackernews', '{}', 1, :now)"
            ),
            {"id": source_id, "now": now},
        )
        connection.execute(
            text(
                'INSERT INTO research_projects '
                '(id, name, description, source_type, query, "limit", cadence, labels_json, '
                "enabled, last_scan_id, created_at, updated_at, schedule_interval_hours, "
                "last_run_at, next_run_at, run_count) VALUES "
                "(:id, 'Legacy project', NULL, 'hackernews', 'ask', 10, 'manual', '[]', "
                "1, NULL, :now, :now, NULL, NULL, NULL, 0)"
            ),
            {"id": project_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO scan_jobs "
                "(id, source_id, status, query, started_at, finished_at, error_message, "
                "items_found, items_saved, signals_detected, clusters_created, "
                "opportunities_created, outcome_message) VALUES "
                "(:id, :source_id, 'completed', 'ask', :now, :now, NULL, "
                "1, 1, 0, 0, 0, 'complete')"
            ),
            {"id": scan_id, "source_id": source_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO normalized_items "
                "(id, source, external_id, url, title, body, author_hash, score, "
                "comments_count, created_at, fetched_at, text_hash, language, tags) VALUES "
                "(:id, 'hackernews', '42', 'https://example.test/42', 'Legacy item', "
                "'Legacy body', NULL, NULL, NULL, :now, :now, :text_hash, 'en', '[]')"
            ),
            {"id": item_id, "now": now, "text_hash": "a" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO scan_items (scan_id, item_id, created_in_scan) "
                "VALUES (:scan_id, :item_id, 1)"
            ),
            {"scan_id": scan_id, "item_id": item_id},
        )
    engine.dispose()

    run_alembic(database_url, "upgrade", "head")
    upgraded = create_engine(database_url)
    upgraded_inspector = inspect(upgraded)
    assert "discourse_source_state" in upgraded_inspector.get_table_names()
    assert "source_id" in {
        column["name"] for column in upgraded_inspector.get_columns("research_projects")
    }
    assert "source_origin" in {
        column["name"] for column in upgraded_inspector.get_columns("research_project_runs")
    }
    assert {
        "observed_source",
        "observed_external_id",
        "observed_url",
    }.issubset(
        {
            column["name"]
            for column in upgraded_inspector.get_columns("scan_items")
        }
    )
    with upgraded.connect() as connection:
        preserved = connection.execute(
            text(
                "SELECT name, source_type, source_id FROM research_projects WHERE id = :id"
            ),
            {"id": project_id},
        ).one()
        preserved_observation = connection.execute(
            text(
                "SELECT created_in_scan, observed_source, observed_external_id, observed_url "
                "FROM scan_items WHERE scan_id = :scan_id AND item_id = :item_id"
            ),
            {"scan_id": scan_id, "item_id": item_id},
        ).one()
    assert preserved == ("Legacy project", "hackernews", None)
    assert preserved_observation == (True, None, None, None)
    upgraded.dispose()

    run_alembic(database_url, "downgrade", "0007_opportunity_threads")
    downgraded = create_engine(database_url)
    downgraded_inspector = inspect(downgraded)
    assert "discourse_source_state" not in downgraded_inspector.get_table_names()
    assert "source_id" not in {
        column["name"] for column in downgraded_inspector.get_columns("research_projects")
    }
    assert "source_origin" not in {
        column["name"] for column in downgraded_inspector.get_columns("research_project_runs")
    }
    assert "observed_source" not in {
        column["name"] for column in downgraded_inspector.get_columns("scan_items")
    }
    with downgraded.connect() as connection:
        assert connection.scalar(
            text("SELECT name FROM research_projects WHERE id = :id"),
            {"id": project_id},
        ) == "Legacy project"
        assert connection.scalar(
            text(
                "SELECT created_in_scan FROM scan_items "
                "WHERE scan_id = :scan_id AND item_id = :item_id"
            ),
            {"scan_id": scan_id, "item_id": item_id},
        ) == 1
    downgraded.dispose()


@pytest.mark.parametrize(
    ("overrides",),
    [
        ({"scheme": "http"},),
        ({"host": "Forum.Example"},),
        ({"port": 0},),
        ({"authorized_at": "2026-07-11T12:00:00+00:00"},),
        ({"last_failure_code": "raw_exception"},),
        ({"last_http_status": 700},),
        ({"last_failure_message": "x" * 501},),
    ],
)
def test_discourse_source_state_constraints_are_portable(tmp_path, overrides) -> None:
    database_url = f"sqlite:///{tmp_path / 'discourse-constraints.db'}"
    run_alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    source_id = "30000000000000000000000000000000"
    now = "2026-07-11T12:00:00+00:00"
    values = {
        "source_id": source_id,
        "scheme": "https",
        "host": "forum.example",
        "port": 443,
        "authorized_at": None,
        "terms_confirmed_at": None,
        "last_failure_code": None,
        "last_failure_message": None,
        "last_http_status": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources (id, name, type, config_json, enabled, created_at) "
                "VALUES (:id, 'Forum', 'discourse', '{}', 1, :now)"
            ),
            {"id": source_id, "now": now},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO discourse_source_state "
                "(source_id, scheme, host, port, authorized_at, terms_confirmed_at, "
                "last_success_at, last_failure_at, last_failure_code, "
                "last_failure_message, last_http_status, retry_after_at, created_at, updated_at) "
                "VALUES (:source_id, :scheme, :host, :port, :authorized_at, "
                ":terms_confirmed_at, NULL, NULL, :last_failure_code, "
                ":last_failure_message, :last_http_status, NULL, :created_at, :updated_at)"
            ),
            values,
        )
    engine.dispose()
