from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models import all_models  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "apps" / "api"

PACKET_COLUMNS = {
    "id",
    "project_id",
    "run_id",
    "thread_id",
    "snapshot_id",
    "lineage_status",
    "generation_mode",
    "schema_version",
    "tasksignal_version",
    "template_version",
    "source_snapshot_json",
    "artifacts_json",
    "manifest_json",
    "manifest_sha256",
    "enhancement_status",
    "enhanced_artifacts_json",
    "enhancement_provider",
    "enhancement_model",
    "enhancement_template_version",
    "generated_at",
    "created_at",
}

INSERT_PACKET_SQL = text(
    "INSERT INTO build_packets "
    "(id, project_id, run_id, thread_id, snapshot_id, lineage_status, generation_mode, "
    "schema_version, tasksignal_version, template_version, source_snapshot_json, "
    "artifacts_json, manifest_json, manifest_sha256, enhancement_status, "
    "enhanced_artifacts_json, enhancement_provider, enhancement_model, "
    "enhancement_template_version, generated_at, created_at) VALUES "
    "(:id, :project_id, :run_id, :thread_id, :snapshot_id, :lineage_status, :generation_mode, "
    ":schema_version, :tasksignal_version, :template_version, :source_snapshot_json, "
    ":artifacts_json, :manifest_json, :manifest_sha256, :enhancement_status, "
    ":enhanced_artifacts_json, :enhancement_provider, :enhancement_model, "
    ":enhancement_template_version, :generated_at, :created_at)"
)


def run_alembic(database_url: str, *args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
    )


def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def insert_untracked_snapshot(
    connection: Connection,
    *,
    cluster_id: str,
    thread_id: str,
    snapshot_id: str,
    title: str,
) -> None:
    now = "2026-07-11T12:00:00+00:00"
    connection.execute(
        text(
            "INSERT INTO clusters "
            "(id, scan_id, title, summary, centroid_embedding, size, created_at, updated_at) "
            "VALUES (:id, NULL, :title, 'Summary', NULL, 1, :now, :now)"
        ),
        {"id": cluster_id, "title": title, "now": now},
    )
    connection.execute(
        text(
            "INSERT INTO opportunity_threads "
            "(id, project_id, current_snapshot_id, lineage_status, review_state, "
            "review_note, decision_updated_at, version, created_at, updated_at) VALUES "
            "(:id, NULL, NULL, 'untracked', 'build_candidate', 'Private local note', "
            ":now, 1, :now, :now)"
        ),
        {"id": thread_id, "now": now},
    )
    connection.execute(
        text(
            "INSERT INTO opportunities "
            "(id, thread_id, run_id, scan_id, evidence_hash, content_hash, match_method, "
            "match_confidence, match_margin, centroid_similarity, evidence_jaccard, "
            "title_jaccard, embedding_model, embedding_backend, cluster_id, title, "
            "problem_statement, target_user, current_workaround, suggested_mvp, why_now, "
            "feasibility_score, opportunity_score, competition_notes, "
            "scoring_breakdown_json, generated_prompt, review_state, review_note, "
            "decision_updated_at, created_at, updated_at) VALUES "
            "(:id, :thread_id, NULL, NULL, :evidence_hash, :content_hash, "
            "'legacy_backfill', NULL, NULL, NULL, NULL, NULL, NULL, NULL, :cluster_id, "
            ":title, 'Problem', 'Builder', 'Manual', 'MVP', 'Now', 0.8, 0.7, "
            "'Narrow', '{}', '# Build', 'build_candidate', 'Snapshot note', :now, "
            ":now, :now)"
        ),
        {
            "id": snapshot_id,
            "thread_id": thread_id,
            "cluster_id": cluster_id,
            "title": title,
            "evidence_hash": "e" * 64,
            "content_hash": "c" * 64,
            "now": now,
        },
    )
    connection.execute(
        text(
            "UPDATE opportunity_threads SET current_snapshot_id = :snapshot_id "
            "WHERE id = :thread_id"
        ),
        {"snapshot_id": snapshot_id, "thread_id": thread_id},
    )


def packet_values(
    *,
    packet_id: str,
    thread_id: str,
    snapshot_id: str,
    **overrides: Any,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "id": packet_id,
        "project_id": None,
        "run_id": None,
        "thread_id": thread_id,
        "snapshot_id": snapshot_id,
        "lineage_status": "untracked",
        "generation_mode": "deterministic",
        "schema_version": "tasksignal.build-packet/v1",
        "tasksignal_version": "1.0.0a1",
        "template_version": "deterministic-v1",
        "source_snapshot_json": "{}",
        "artifacts_json": '{"README.md":{"content":"# Packet"}}',
        "manifest_json": '{"schema_version":"tasksignal.build-packet/v1"}',
        "manifest_sha256": "a" * 64,
        "enhancement_status": "not_requested",
        "enhanced_artifacts_json": None,
        "enhancement_provider": None,
        "enhancement_model": None,
        "enhancement_template_version": None,
        "generated_at": "2026-07-11T12:30:00+00:00",
        "created_at": "2026-07-11T12:30:01+00:00",
    }
    values.update(overrides)
    return values


def test_models_expose_immutable_build_packet_schema() -> None:
    tables = Base.metadata.tables

    assert "build_packets" in tables
    assert set(tables["build_packets"].columns.keys()) == PACKET_COLUMNS
    assert "updated_at" not in tables["build_packets"].columns
    assert "enhancement_error" not in tables["build_packets"].columns
    for name in ("source_snapshot_json", "artifacts_json", "manifest_json"):
        assert tables["build_packets"].columns[name].type.none_as_null is True

    opportunity_uniques = {
        tuple(constraint.columns.keys())
        for constraint in tables["opportunities"].constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("id", "thread_id") in opportunity_uniques

    foreign_keys = {
        (
            tuple(constraint.column_keys),
            constraint.referred_table.name,
            tuple(element.column.name for element in constraint.elements),
        )
        for constraint in tables["build_packets"].foreign_key_constraints
    }
    assert (("project_id",), "research_projects", ("id",)) in foreign_keys
    assert (("run_id",), "research_project_runs", ("id",)) in foreign_keys
    assert (("thread_id",), "opportunity_threads", ("id",)) in foreign_keys
    assert (
        ("snapshot_id", "thread_id"),
        "opportunities",
        ("id", "thread_id"),
    ) in foreign_keys
    assert (
        ("run_id", "project_id"),
        "research_project_runs",
        ("id", "project_id"),
    ) in foreign_keys
    assert (
        ("thread_id", "project_id"),
        "opportunity_threads",
        ("id", "project_id"),
    ) in foreign_keys
    assert (
        ("thread_id", "lineage_status"),
        "opportunity_threads",
        ("id", "lineage_status"),
    ) in foreign_keys


def test_build_packet_migration_preserves_v1_data_and_downgrades(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'build-packets.db'}"
    run_alembic(database_url, "upgrade", "0007_discourse_sources")
    engine = create_engine(database_url)
    ids = {
        "cluster": "10000000000000000000000000000000",
        "thread": "20000000000000000000000000000000",
        "snapshot": "30000000000000000000000000000000",
        "packet": "40000000000000000000000000000000",
    }
    with engine.begin() as connection:
        insert_untracked_snapshot(
            connection,
            cluster_id=ids["cluster"],
            thread_id=ids["thread"],
            snapshot_id=ids["snapshot"],
            title="Preserved opportunity",
        )
    engine.dispose()

    run_alembic(database_url, "upgrade", "head")
    upgraded = create_engine(database_url)
    inspector = inspect(upgraded)
    assert "build_packets" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns("build_packets")} == (
        PACKET_COLUMNS
    )
    assert ("id", "thread_id") in {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("opportunities")
    }
    packet_foreign_keys = inspector.get_foreign_keys("build_packets")
    assert any(
        foreign_key["constrained_columns"] == ["snapshot_id", "thread_id"]
        and foreign_key["referred_table"] == "opportunities"
        and foreign_key["referred_columns"] == ["id", "thread_id"]
        for foreign_key in packet_foreign_keys
    )
    assert any(
        foreign_key["constrained_columns"] == ["run_id", "project_id"]
        and foreign_key["referred_table"] == "research_project_runs"
        and foreign_key["referred_columns"] == ["id", "project_id"]
        for foreign_key in packet_foreign_keys
    )
    with upgraded.begin() as connection:
        connection.execute(
            INSERT_PACKET_SQL,
            packet_values(
                packet_id=ids["packet"],
                thread_id=ids["thread"],
                snapshot_id=ids["snapshot"],
            ),
        )
    with upgraded.connect() as connection:
        preserved = connection.execute(
            text(
                "SELECT o.title, o.review_note, t.review_note, t.current_snapshot_id "
                "FROM opportunities o JOIN opportunity_threads t ON t.id = o.thread_id "
                "WHERE o.id = :snapshot_id"
            ),
            {"snapshot_id": ids["snapshot"]},
        ).one()
        stored_packet = connection.execute(
            text(
                "SELECT thread_id, snapshot_id, generation_mode, enhancement_status "
                "FROM build_packets WHERE id = :packet_id"
            ),
            {"packet_id": ids["packet"]},
        ).one()
    assert preserved == (
        "Preserved opportunity",
        "Snapshot note",
        "Private local note",
        ids["snapshot"],
    )
    assert stored_packet == (
        ids["thread"],
        ids["snapshot"],
        "deterministic",
        "not_requested",
    )
    upgraded.dispose()

    run_alembic(database_url, "downgrade", "0007_discourse_sources")
    downgraded = create_engine(database_url)
    downgraded_inspector = inspect(downgraded)
    assert "build_packets" not in downgraded_inspector.get_table_names()
    assert ("id", "thread_id") not in {
        tuple(constraint["column_names"])
        for constraint in downgraded_inspector.get_unique_constraints("opportunities")
    }
    with downgraded.connect() as connection:
        preserved_after_downgrade = connection.execute(
            text(
                "SELECT o.title, t.current_snapshot_id "
                "FROM opportunities o JOIN opportunity_threads t ON t.id = o.thread_id "
                "WHERE o.id = :snapshot_id"
            ),
            {"snapshot_id": ids["snapshot"]},
        ).one()
    assert preserved_after_downgrade == ("Preserved opportunity", ids["snapshot"])
    downgraded.dispose()


def test_build_packet_constraints_and_snapshot_thread_link_are_portable(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'build-packet-constraints.db'}"
    run_alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    from sqlalchemy import event

    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    ids = {
        "cluster_one": "10000000000000000000000000000001",
        "thread_one": "20000000000000000000000000000001",
        "snapshot_one": "30000000000000000000000000000001",
        "cluster_two": "10000000000000000000000000000002",
        "thread_two": "20000000000000000000000000000002",
        "snapshot_two": "30000000000000000000000000000002",
    }
    with engine.begin() as connection:
        insert_untracked_snapshot(
            connection,
            cluster_id=ids["cluster_one"],
            thread_id=ids["thread_one"],
            snapshot_id=ids["snapshot_one"],
            title="First opportunity",
        )
        insert_untracked_snapshot(
            connection,
            cluster_id=ids["cluster_two"],
            thread_id=ids["thread_two"],
            snapshot_id=ids["snapshot_two"],
            title="Second opportunity",
        )

    allowed_packets = (
        packet_values(
            packet_id="40000000000000000000000000000001",
            thread_id=ids["thread_one"],
            snapshot_id=ids["snapshot_one"],
        ),
        packet_values(
            packet_id="40000000000000000000000000000002",
            thread_id=ids["thread_one"],
            snapshot_id=ids["snapshot_one"],
            generation_mode="configured_ai",
            enhancement_status="generated",
            enhanced_artifacts_json='{"enhanced/README.md":{"content":"# Enhanced"}}',
            enhancement_provider="ollama",
            enhancement_model="qwen3",
            enhancement_template_version="enhancement-v1",
        ),
        packet_values(
            packet_id="40000000000000000000000000000003",
            thread_id=ids["thread_one"],
            snapshot_id=ids["snapshot_one"],
            generation_mode="configured_ai",
            enhancement_status="fallback",
            enhancement_provider="openai",
            enhancement_model="gpt-example",
            enhancement_template_version="enhancement-v1",
        ),
    )
    with engine.begin() as connection:
        for values in allowed_packets:
            connection.execute(INSERT_PACKET_SQL, values)

    invalid_overrides = (
        {"generation_mode": "automatic"},
        {"tasksignal_version": ""},
        {"manifest_sha256": "a" * 63},
        {"manifest_sha256": "A" * 64},
        {"manifest_sha256": "z" * 64},
        {"lineage_status": "complete"},
        {"lineage_status": "unknown"},
        {"enhancement_status": "generated"},
        {
            "generation_mode": "configured_ai",
            "enhancement_status": "generated",
            "enhancement_provider": "ollama",
            "enhancement_model": "qwen3",
            "enhancement_template_version": "enhancement-v1",
        },
        {
            "generation_mode": "configured_ai",
            "enhancement_status": "fallback",
            "enhanced_artifacts_json": "{}",
            "enhancement_provider": "ollama",
            "enhancement_model": "qwen3",
            "enhancement_template_version": "enhancement-v1",
        },
    )
    for index, overrides in enumerate(invalid_overrides, start=10):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                INSERT_PACKET_SQL,
                packet_values(
                    packet_id=f"400000000000000000000000000000{index}",
                    thread_id=ids["thread_one"],
                    snapshot_id=ids["snapshot_one"],
                    **overrides,
                ),
            )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            INSERT_PACKET_SQL,
            packet_values(
                packet_id="40000000000000000000000000000099",
                thread_id=ids["thread_two"],
                snapshot_id=ids["snapshot_one"],
            ),
        )

    engine.dispose()
