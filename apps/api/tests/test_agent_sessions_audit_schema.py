import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.base import Base
from app.models import all_models  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "apps" / "api"


def run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
        capture_output=True,
        text=True,
    )


def enable_sqlite_foreign_keys(engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys = ON"))


def pending_session_values(*, session_id: str = "1" * 32) -> dict[str, object]:
    return {
        "id": session_id,
        "process_instance_id": "2" * 32,
        "client_name": "Codex MCP",
        "client_version": "1.0.0",
        "transport": "stdio",
        "secret_hash": "a" * 64,
        "status": "pending",
        "requested_capabilities_json": '["set_opportunity_decision"]',
        "approved_capabilities_json": "[]",
        "approval_source": None,
        "approved_at": None,
        "last_heartbeat_at": "2026-07-11T12:00:00+00:00",
        "expires_at": "2026-07-11T12:01:00+00:00",
        "revoked_at": None,
        "expired_at": None,
        "exited_at": None,
        "version": 1,
        "created_at": "2026-07-11T12:00:00+00:00",
        "updated_at": "2026-07-11T12:00:00+00:00",
    }


def insert_session(connection, values: dict[str, object]) -> None:
    connection.execute(
        text(
            "INSERT INTO agent_sessions "
            "(id, process_instance_id, client_name, client_version, transport, secret_hash, "
            "status, requested_capabilities_json, approved_capabilities_json, "
            "approval_source, approved_at, last_heartbeat_at, expires_at, revoked_at, "
            "expired_at, exited_at, version, created_at, updated_at) VALUES "
            "(:id, :process_instance_id, :client_name, :client_version, :transport, "
            ":secret_hash, :status, :requested_capabilities_json, "
            ":approved_capabilities_json, :approval_source, :approved_at, "
            ":last_heartbeat_at, :expires_at, :revoked_at, :expired_at, :exited_at, :version, "
            ":created_at, :updated_at)"
        ),
        values,
    )


def action_values(
    *,
    event_status: str,
    event_sequence: int,
    action_id: str,
    operation_id: str = "3" * 32,
) -> dict[str, object]:
    return {
        "id": action_id,
        "session_id": "1" * 32,
        "operation_id": operation_id,
        "correlation_id": "4" * 32,
        "event_sequence": event_sequence,
        "event_status": event_status,
        "idempotency_key_hash": "b" * 64,
        "request_hash": "c" * 64,
        "capability": "set_opportunity_decision",
        "tool_name": "set_opportunity_decision",
        "target_type": "opportunity_thread",
        "target_id": "5" * 32,
        "request_summary_json": '{"fields":["decision"]}',
        "result_summary_json": "{}",
        "error_code": None,
        "created_at": "2026-07-11T12:00:00+00:00",
    }


def insert_action(connection, values: dict[str, object]) -> None:
    connection.execute(
        text(
            "INSERT INTO agent_actions "
            "(id, session_id, operation_id, correlation_id, event_sequence, event_status, "
            "idempotency_key_hash, request_hash, capability, tool_name, target_type, "
            "target_id, request_summary_json, result_summary_json, error_code, created_at) "
            "VALUES (:id, :session_id, :operation_id, :correlation_id, :event_sequence, "
            ":event_status, :idempotency_key_hash, :request_hash, :capability, :tool_name, "
            ":target_type, :target_id, :request_summary_json, :result_summary_json, "
            ":error_code, :created_at)"
        ),
        values,
    )


def test_models_expose_agent_session_audit_and_version_contract() -> None:
    tables = Base.metadata.tables
    assert set(tables["agent_sessions"].columns.keys()) == {
        "id",
        "process_instance_id",
        "client_name",
        "client_version",
        "transport",
        "secret_hash",
        "status",
        "requested_capabilities_json",
        "approved_capabilities_json",
        "approval_source",
        "approved_at",
        "last_heartbeat_at",
        "expires_at",
        "revoked_at",
        "expired_at",
        "exited_at",
        "version",
        "created_at",
        "updated_at",
    }
    assert set(tables["agent_actions"].columns.keys()) == {
        "id",
        "session_id",
        "operation_id",
        "correlation_id",
        "event_sequence",
        "event_status",
        "idempotency_key_hash",
        "request_hash",
        "capability",
        "tool_name",
        "target_type",
        "target_id",
        "request_summary_json",
        "result_summary_json",
        "error_code",
        "created_at",
    }
    assert "version" in tables["research_projects"].columns
    assert {"actor_type", "agent_session_id", "version"}.issubset(
        tables["labels"].columns.keys()
    )
    assert "agent_session_id" in tables["opportunity_decision_events"].columns
    decision_index = next(
        index
        for index in tables["opportunity_decision_events"].indexes
        if index.name == "ix_opportunity_decision_events_thread_created"
    )
    assert [column.name for column in decision_index.columns] == [
        "thread_id",
        "created_at",
        "id",
    ]


def test_migration_backfills_human_label_versions_and_downgrades_cleanly(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'agent-schema.db'}"
    run_alembic(database_url, "upgrade", "0008_build_packets")
    engine = create_engine(database_url)
    now = "2026-07-11T12:00:00+00:00"
    project_id = "1" * 32
    item_id = "2" * 32
    with engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO research_projects '
                '(id, name, description, source_type, query, "limit", cadence, '
                "schedule_interval_hours, labels_json, enabled, source_id, last_scan_id, "
                "last_run_at, next_run_at, run_count, created_at, updated_at) VALUES "
                "(:id, 'Legacy project', NULL, 'mock', 'test', 10, 'manual', NULL, "
                "'[]', 1, NULL, NULL, NULL, NULL, 0, :now, :now)"
            ),
            {"id": project_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO normalized_items "
                "(id, source, external_id, url, title, body, author_hash, score, "
                "comments_count, created_at, fetched_at, text_hash, language, tags) VALUES "
                "(:id, 'mock', 'one', 'https://example.test/one', 'Legacy', 'Body', "
                "NULL, NULL, NULL, :now, :now, :hash, 'en', '[]')"
            ),
            {"id": item_id, "now": now, "hash": "d" * 64},
        )
        for label_id, label in (("3" * 32, "true_signal"), ("4" * 32, "false_positive")):
            connection.execute(
                text(
                    "INSERT INTO labels (id, item_id, label, user_note, created_at) "
                    "VALUES (:id, :item_id, :label, NULL, :now)"
                ),
                {"id": label_id, "item_id": item_id, "label": label, "now": now},
            )
    engine.dispose()

    run_alembic(database_url, "upgrade", "0009_agent_sessions_audit")
    upgraded = create_engine(database_url)
    inspector = inspect(upgraded)
    assert {"agent_sessions", "agent_actions"}.issubset(inspector.get_table_names())
    label_session_fk = next(
        foreign_key
        for foreign_key in inspector.get_foreign_keys("labels")
        if foreign_key["referred_table"] == "agent_sessions"
    )
    decision_session_fk = next(
        foreign_key
        for foreign_key in inspector.get_foreign_keys("opportunity_decision_events")
        if foreign_key["referred_table"] == "agent_sessions"
    )
    assert label_session_fk["options"].get("ondelete") == "RESTRICT"
    assert decision_session_fk["options"].get("ondelete") == "RESTRICT"
    with upgraded.connect() as connection:
        labels = connection.execute(
            text(
                "SELECT id, actor_type, agent_session_id, version FROM labels "
                "WHERE item_id = :item_id ORDER BY version"
            ),
            {"item_id": item_id},
        ).all()
        project_version = connection.scalar(
            text("SELECT version FROM research_projects WHERE id = :id"),
            {"id": project_id},
        )
    assert labels == [("3" * 32, "human", None, 1), ("4" * 32, "human", None, 2)]
    assert project_version == 1
    upgraded.dispose()

    run_alembic(database_url, "downgrade", "0008_build_packets")
    downgraded = create_engine(database_url)
    downgraded_inspector = inspect(downgraded)
    assert "agent_sessions" not in downgraded_inspector.get_table_names()
    assert "agent_actions" not in downgraded_inspector.get_table_names()
    assert "version" not in {
        column["name"] for column in downgraded_inspector.get_columns("research_projects")
    }
    assert {"actor_type", "agent_session_id", "version"}.isdisjoint(
        column["name"] for column in downgraded_inspector.get_columns("labels")
    )
    with downgraded.connect() as connection:
        preserved = connection.execute(
            text("SELECT id, label FROM labels WHERE item_id = :item_id ORDER BY id"),
            {"item_id": item_id},
        ).all()
    assert preserved == [("3" * 32, "true_signal"), ("4" * 32, "false_positive")]
    downgraded.dispose()


def test_agent_action_event_stream_allows_terminal_append_but_not_duplicate_reservation(
    tmp_path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'event-stream.db'}"
    run_alembic(database_url, "upgrade", "0009_agent_sessions_audit")
    engine = create_engine(database_url)
    enable_sqlite_foreign_keys(engine)
    with engine.begin() as connection:
        insert_session(connection, pending_session_values())
        insert_action(
            connection,
            action_values(event_status="reserved", event_sequence=1, action_id="6" * 32),
        )
        insert_action(
            connection,
            action_values(event_status="succeeded", event_sequence=2, action_id="7" * 32),
        )
        insert_action(
            connection,
            action_values(event_status="replayed", event_sequence=3, action_id="8" * 32),
        )

    duplicate = action_values(
        event_status="reserved",
        event_sequence=1,
        action_id="9" * 32,
        operation_id="a" * 32,
    )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert_action(connection, duplicate)

    with engine.connect() as connection:
        events = connection.execute(
            text(
                "SELECT event_sequence, event_status FROM agent_actions "
                "WHERE operation_id = :operation_id ORDER BY event_sequence"
            ),
            {"operation_id": "3" * 32},
        ).all()
    assert events == [(1, "reserved"), (2, "succeeded"), (3, "replayed")]
    engine.dispose()


def test_agent_action_operation_allows_only_one_core_terminal_event(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'terminal-event.db'}"
    run_alembic(database_url, "upgrade", "0009_agent_sessions_audit")
    engine = create_engine(database_url)
    enable_sqlite_foreign_keys(engine)
    with engine.begin() as connection:
        insert_session(connection, pending_session_values())
        insert_action(
            connection,
            action_values(event_status="reserved", event_sequence=1, action_id="6" * 32),
        )
        insert_action(
            connection,
            action_values(event_status="succeeded", event_sequence=2, action_id="7" * 32),
        )
        insert_action(
            connection,
            action_values(event_status="replayed", event_sequence=3, action_id="8" * 32),
        )

    duplicate_terminal = action_values(
        event_status="failed",
        event_sequence=4,
        action_id="9" * 32,
    )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert_action(connection, duplicate_terminal)

    with engine.connect() as connection:
        events = connection.execute(
            text(
                "SELECT event_sequence, event_status FROM agent_actions "
                "WHERE operation_id = :operation_id ORDER BY event_sequence"
            ),
            {"operation_id": "3" * 32},
        ).all()
    assert events == [(1, "reserved"), (2, "succeeded"), (3, "replayed")]
    engine.dispose()


@pytest.mark.parametrize(
    ("table", "values", "statement"),
    [
        (
            "agent_sessions",
            {**pending_session_values(), "secret_hash": "not-a-sha256"},
            insert_session,
        ),
        (
            "agent_sessions",
            {**pending_session_values(), "status": "approved"},
            insert_session,
        ),
        (
            "agent_actions",
            action_values(event_status="unknown", event_sequence=2, action_id="b" * 32),
            insert_action,
        ),
        (
            "agent_actions",
            action_values(event_status="succeeded", event_sequence=1, action_id="c" * 32),
            insert_action,
        ),
    ],
)
def test_session_and_action_shape_constraints_are_enforced(
    tmp_path,
    table,
    values,
    statement,
) -> None:
    database_url = f"sqlite:///{tmp_path / f'{table}.db'}"
    run_alembic(database_url, "upgrade", "0009_agent_sessions_audit")
    engine = create_engine(database_url)
    enable_sqlite_foreign_keys(engine)
    with engine.begin() as connection:
        if table == "agent_actions":
            insert_session(connection, pending_session_values())
    with pytest.raises(IntegrityError), engine.begin() as connection:
        statement(connection, values)
    engine.dispose()


def test_actor_session_shape_and_restrict_foreign_keys_are_enforced(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'actor-shape.db'}"
    run_alembic(database_url, "upgrade", "0009_agent_sessions_audit")
    engine = create_engine(database_url)
    enable_sqlite_foreign_keys(engine)
    now = "2026-07-11T12:00:00+00:00"
    item_id = "d" * 32
    with engine.begin() as connection:
        insert_session(connection, pending_session_values())
        connection.execute(
            text(
                "INSERT INTO normalized_items "
                "(id, source, external_id, url, title, body, author_hash, score, "
                "comments_count, created_at, fetched_at, text_hash, language, tags) VALUES "
                "(:id, 'mock', 'one', 'https://example.test/one', 'Item', 'Body', NULL, "
                "NULL, NULL, :now, :now, :hash, 'en', '[]')"
            ),
            {"id": item_id, "now": now, "hash": "e" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO labels "
                "(id, item_id, label, user_note, actor_type, agent_session_id, version, "
                "created_at) VALUES "
                "(:id, :item, 'true_signal', NULL, 'agent', :session, 1, :now)"
            ),
            {"id": "e" * 32, "item": item_id, "session": "1" * 32, "now": now},
        )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO labels "
                "(id, item_id, label, user_note, actor_type, agent_session_id, version, "
                "created_at) VALUES "
                "(:id, :item, 'true_signal', NULL, 'human', :session, 2, :now)"
            ),
            {"id": "f" * 32, "item": item_id, "session": "1" * 32, "now": now},
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text("DELETE FROM agent_sessions WHERE id = :id"),
            {"id": "1" * 32},
        )
    engine.dispose()


def test_agent_schema_constraints_compile_for_postgresql_and_offline_migration() -> None:
    dialect = postgresql.dialect()
    session_ddl = str(CreateTable(Base.metadata.tables["agent_sessions"]).compile(dialect=dialect))
    action_table = Base.metadata.tables["agent_actions"]
    action_ddl = str(CreateTable(action_table).compile(dialect=dialect))
    reserved_index = next(
        index for index in action_table.indexes if index.name == "uq_agent_actions_reserved_key"
    )
    terminal_index = next(
        index
        for index in action_table.indexes
        if index.name == "uq_agent_actions_terminal_operation"
    )
    reserved_index_ddl = str(CreateIndex(reserved_index).compile(dialect=dialect))
    terminal_index_ddl = str(CreateIndex(terminal_index).compile(dialect=dialect))
    assert "GLOB" not in (
        session_ddl + action_ddl + reserved_index_ddl + terminal_index_ddl
    )
    assert "event_status IN" in action_ddl
    assert "WHERE event_status = 'reserved'" in reserved_index_ddl
    assert (
        "WHERE event_status IN ('succeeded', 'failed', 'denied')"
        in terminal_index_ddl
    )

    result = run_alembic(
        "postgresql+psycopg://tasksignal:tasksignal@localhost/tasksignal",
        "upgrade",
        "0008_build_packets:0009_agent_sessions_audit",
        "--sql",
    )
    assert "CREATE TABLE agent_sessions" in result.stdout
    assert "CREATE TABLE agent_actions" in result.stdout
    assert "WHERE event_status = 'reserved'" in result.stdout
    assert (
        "WHERE event_status IN ('succeeded', 'failed', 'denied')"
        in result.stdout
    )
