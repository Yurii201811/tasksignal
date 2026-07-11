#!/usr/bin/env python3
"""Run destructive, database-isolated TaskSignal migrations against PostgreSQL.

The harness deliberately accepts the database URL only through an environment
variable so credentials do not appear in the process list. Every case runs in a
fresh database and all databases are dropped in a ``finally`` block.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from alembic import command
from sqlalchemy import Engine, create_engine, inspect, make_url, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from app.packaged_runtime import (
    MigrationSafetyError,
    inspect_schema,
    migrate_database,
    packaged_alembic_config,
)

DEFAULT_DATABASE_URL_ENV = "TASKSIGNAL_POSTGRES_REHEARSAL_URL"
V02_REVISION = "0006_decision_workbench"

_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_FIXED_IDS = {
    "item": uuid.UUID("10000000-0000-0000-0000-000000000001"),
    "cluster": uuid.UUID("20000000-0000-0000-0000-000000000002"),
    "opportunity": uuid.UUID("30000000-0000-0000-0000-000000000003"),
}
_FIXED_TIME = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
_FIXED_TEXT_HASH = "a" * 64


@dataclass(frozen=True)
class CaseResult:
    name: str
    state_before: str
    state_after: str
    assertions: tuple[str, ...]


def _normalized_postgresql_url(value: str) -> URL:
    try:
        url = make_url(value)
    except Exception as exc:
        raise ValueError("The rehearsal database URL is invalid.") from exc
    if url.get_backend_name() != "postgresql":
        raise ValueError("The rehearsal requires a PostgreSQL database URL.")
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("The rehearsal requires the psycopg 3 PostgreSQL driver.")
    if not url.database:
        raise ValueError("The rehearsal database URL must name a database.")
    return url


def _render_url(url: URL) -> str:
    """Render a connection URL only for an in-process database client."""
    return url.render_as_string(hide_password=False)


def _case_database_url(base_url: URL, database_name: str) -> str:
    _validate_identifier(database_name)
    return _render_url(base_url.set(database=database_name))


def _validate_identifier(value: str) -> None:
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError("Unsafe PostgreSQL database identifier.")


def _quoted_identifier(connection: Any, identifier: str) -> str:
    _validate_identifier(identifier)
    return connection.dialect.identifier_preparer.quote(identifier)


def _safe_failure_message(error: BaseException, database_url: URL) -> str:
    message = str(error) or error.__class__.__name__
    rendered = _render_url(database_url)
    replacements = {rendered}
    if database_url.password:
        password = str(database_url.password)
        replacements.update({password, quote(password, safe="")})
    for sensitive in sorted(replacements, key=len, reverse=True):
        if sensitive:
            message = message.replace(sensitive, "<redacted>")
    message = re.sub(
        r"(?i)(postgres(?:ql)?(?:\+[^:]+)?://[^:/@\s]+:)[^@\s]+@",
        r"\1<redacted>@",
        message,
    )
    message = re.sub(r"(?i)(password\s*=\s*)[^\s,;]+", r"\1<redacted>", message)
    return message


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _fresh_database_case(database_url: str) -> CaseResult:
    before = inspect_schema(database_url)
    _assert(before.state == "empty", f"expected empty schema, got {before.state}")

    migrated = migrate_database(database_url)
    _assert(migrated.migrated, "fresh schema did not report a migration")
    _assert(
        migrated.backup_path is None,
        "PostgreSQL migration unexpectedly created a backup",
    )
    _assert(
        migrated.status.state == "current", "fresh schema did not reach packaged head"
    )

    engine = create_engine(database_url, poolclass=NullPool)
    try:
        tables = _table_names(engine)
        required = {
            "alembic_version",
            "research_project_runs",
            "opportunity_threads",
            "build_packets",
            "agent_sessions",
            "agent_actions",
        }
        _assert(required <= tables, "fresh schema is missing v1 tables")
    finally:
        engine.dispose()

    repeated = migrate_database(database_url)
    _assert(not repeated.migrated, "identical second migration was not a no-op")
    _assert(
        repeated.status.current_revision == before.head_revision,
        "head revision drifted",
    )
    return CaseResult(
        name="fresh_empty_to_head",
        state_before=before.state,
        state_after=repeated.status.state,
        assertions=("packaged_head", "required_tables", "idempotent_rerun"),
    )


def _seed_v02_representative_row(database_url: str) -> None:
    command.upgrade(packaged_alembic_config(database_url), V02_REVISION)
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO normalized_items "
                    "(id, source, external_id, url, title, body, author_hash, score, "
                    "comments_count, created_at, fetched_at, text_hash, language, tags) VALUES "
                    "(:id, 'fixture', 'v02-evidence', 'https://example.test/evidence', "
                    "'Preserved evidence', 'Representative v0.2 evidence', NULL, 7, 2, "
                    ":created_at, :created_at, :text_hash, 'en', CAST(:tags AS jsonb))"
                ),
                {
                    "id": _FIXED_IDS["item"],
                    "created_at": _FIXED_TIME,
                    "text_hash": _FIXED_TEXT_HASH,
                    "tags": json.dumps(["migration-rehearsal"]),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO clusters "
                    "(id, title, summary, centroid_embedding, size, created_at, updated_at) "
                    "VALUES (:id, 'Preserved cluster', 'Representative v0.2 cluster', "
                    "NULL, 1, :created_at, :created_at)"
                ),
                {"id": _FIXED_IDS["cluster"], "created_at": _FIXED_TIME},
            )
            connection.execute(
                text(
                    "INSERT INTO cluster_items (cluster_id, item_id, similarity_score) "
                    "VALUES (:cluster_id, :item_id, 0.95)"
                ),
                {
                    "cluster_id": _FIXED_IDS["cluster"],
                    "item_id": _FIXED_IDS["item"],
                },
            )
            connection.execute(
                text(
                    "INSERT INTO opportunities "
                    "(id, cluster_id, title, problem_statement, target_user, current_workaround, "
                    "suggested_mvp, why_now, feasibility_score, opportunity_score, "
                    "competition_notes, scoring_breakdown_json, generated_prompt, review_state, "
                    "review_note, decision_updated_at, created_at, updated_at) VALUES "
                    "(:id, :cluster_id, 'Preserved opportunity', 'Problem', 'Indie builder', "
                    "'Manual research', 'Local workbench', 'Evidence changed', 0.8, 0.75, "
                    "'Narrow market', CAST(:scoring AS jsonb), '# Build', 'promising', "
                    "'local decision note', :created_at, :created_at, :created_at)"
                ),
                {
                    "id": _FIXED_IDS["opportunity"],
                    "cluster_id": _FIXED_IDS["cluster"],
                    "scoring": json.dumps({"readiness": "medium"}, sort_keys=True),
                    "created_at": _FIXED_TIME,
                },
            )
    finally:
        engine.dispose()


def _copied_v02_case(database_url: str) -> CaseResult:
    _seed_v02_representative_row(database_url)
    before = inspect_schema(database_url)
    _assert(before.state == "stale", f"expected stale v0.2 schema, got {before.state}")
    _assert(before.current_revision == V02_REVISION, "v0.2 fixture has wrong revision")

    migrated = migrate_database(database_url)
    _assert(migrated.migrated, "v0.2 schema did not report a migration")
    _assert(
        migrated.status.state == "current", "v0.2 schema did not reach packaged head"
    )
    _assert(
        migrated.backup_path is None,
        "PostgreSQL migration unexpectedly created a backup",
    )

    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT o.title, o.review_state, o.review_note, o.match_method, "
                    "length(o.evidence_hash), t.lineage_status, t.review_state, t.review_note, "
                    "e.event_type, n.text_hash "
                    "FROM opportunities AS o "
                    "JOIN opportunity_threads AS t ON t.id = o.thread_id "
                    "JOIN opportunity_decision_events AS e ON e.thread_id = t.id "
                    "JOIN cluster_items AS ci ON ci.cluster_id = o.cluster_id "
                    "JOIN normalized_items AS n ON n.id = ci.item_id "
                    "WHERE o.id = :opportunity_id"
                ),
                {"opportunity_id": _FIXED_IDS["opportunity"]},
            ).one()
            _assert(row[0] == "Preserved opportunity", "v0.2 opportunity changed")
            _assert(
                row[1:3] == ("promising", "local decision note"),
                "decision data changed",
            )
            _assert(
                row[3:5] == ("legacy_backfill", 64), "thread hashes were not backfilled"
            )
            _assert(
                row[5] == "untracked", "historical lineage was incorrectly inferred"
            )
            _assert(
                row[6:8] == ("promising", "local decision note"), "thread state changed"
            )
            _assert(row[8] == "legacy_backfill", "decision event was not backfilled")
            _assert(row[9] == _FIXED_TEXT_HASH, "representative evidence changed")
    finally:
        engine.dispose()

    return CaseResult(
        name="copied_v02_to_head",
        state_before=before.state,
        state_after=migrated.status.state,
        assertions=("data_preserved", "thread_backfilled", "lineage_untracked"),
    )


def _nonempty_unversioned_case(database_url: str) -> CaseResult:
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE legacy_notes (id integer PRIMARY KEY, note text NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO legacy_notes (id, note) VALUES (1, 'preserve me')"
            )
    finally:
        engine.dispose()

    before = inspect_schema(database_url)
    _assert(
        before.state == "unversioned",
        f"expected unversioned schema, got {before.state}",
    )
    try:
        migrate_database(database_url)
    except MigrationSafetyError as exc:
        _assert(
            exc.code == "postgresql_unversioned_schema",
            f"unexpected refusal code: {exc.code}",
        )
    else:
        raise AssertionError("nonempty unversioned schema was migrated")

    engine = create_engine(database_url, poolclass=NullPool)
    try:
        tables = _table_names(engine)
        _assert(tables == {"legacy_notes"}, "unversioned refusal mutated the schema")
        with engine.connect() as connection:
            note = connection.exec_driver_sql(
                "SELECT note FROM legacy_notes WHERE id = 1"
            ).scalar_one()
        _assert(note == "preserve me", "unversioned refusal changed existing data")
    finally:
        engine.dispose()

    after = inspect_schema(database_url)
    return CaseResult(
        name="nonempty_unversioned_fails_closed",
        state_before=before.state,
        state_after=after.state,
        assertions=("structured_refusal", "no_alembic_stamp", "data_preserved"),
    )


def _unknown_revision_case(database_url: str) -> CaseResult:
    foreign_revision = "foreign_revision_9999"
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE alembic_version ("
                "version_num varchar(32) NOT NULL PRIMARY KEY)"
            )
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": foreign_revision},
            )
    finally:
        engine.dispose()

    before = inspect_schema(database_url)
    _assert(before.state == "unknown", f"expected unknown schema, got {before.state}")
    _assert(
        before.current_revision == foreign_revision, "foreign revision was not observed"
    )
    try:
        migrate_database(database_url)
    except MigrationSafetyError as exc:
        _assert(
            exc.code == "postgresql_unknown_schema",
            f"unexpected refusal code: {exc.code}",
        )
    else:
        raise AssertionError("foreign Alembic revision was migrated")

    engine = create_engine(database_url, poolclass=NullPool)
    try:
        _assert(
            _table_names(engine) == {"alembic_version"},
            "unknown refusal mutated schema",
        )
        with engine.connect() as connection:
            revision = connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
        _assert(revision == foreign_revision, "foreign revision was overwritten")
    finally:
        engine.dispose()

    after = inspect_schema(database_url)
    return CaseResult(
        name="foreign_revision_fails_closed",
        state_before=before.state,
        state_after=after.state,
        assertions=("structured_refusal", "revision_preserved", "no_app_tables"),
    )


def run_rehearsal(database_url_value: str) -> list[CaseResult]:
    base_url = _normalized_postgresql_url(database_url_value)
    admin_engine = create_engine(
        _render_url(base_url),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    namespace = f"ts_rehearsal_{uuid.uuid4().hex[:10]}"
    cases: tuple[tuple[str, Callable[[str], CaseResult]], ...] = (
        (f"{namespace}_fresh", _fresh_database_case),
        (f"{namespace}_v02", _copied_v02_case),
        (f"{namespace}_unversioned", _nonempty_unversioned_case),
        (f"{namespace}_unknown", _unknown_revision_case),
    )
    created_databases: list[str] = []
    try:
        with admin_engine.connect() as connection:
            for database_name, _ in cases:
                quoted = _quoted_identifier(connection, database_name)
                connection.exec_driver_sql(
                    f"CREATE DATABASE {quoted} TEMPLATE template0"
                )
                created_databases.append(database_name)
        return [
            case(_case_database_url(base_url, database_name))
            for database_name, case in cases
        ]
    finally:
        cleanup_errors: list[str] = []
        for database_name in reversed(created_databases):
            try:
                with admin_engine.connect() as connection:
                    quoted = _quoted_identifier(connection, database_name)
                    connection.exec_driver_sql(f"DROP DATABASE {quoted} WITH (FORCE)")
            except Exception as exc:  # pragma: no cover - requires a broken live server
                cleanup_errors.append(_safe_failure_message(exc, base_url))
        admin_engine.dispose()
        if cleanup_errors and sys.exc_info()[0] is None:
            raise RuntimeError(
                "PostgreSQL rehearsal cleanup failed: " + "; ".join(cleanup_errors)
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rehearse TaskSignal packaged migrations on PostgreSQL 16 with pgvector.",
    )
    parser.add_argument(
        "--database-url-env",
        default=DEFAULT_DATABASE_URL_ENV,
        help="Environment variable containing the PostgreSQL URL (default: %(default)s).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    value = os.environ.get(args.database_url_env)
    if not value:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "database_url_missing",
                        "message": f"Set {args.database_url_env} to a PostgreSQL rehearsal database URL.",
                    },
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    try:
        base_url = _normalized_postgresql_url(value)
        results = run_rehearsal(value)
    except Exception as exc:
        try:
            base_url = _normalized_postgresql_url(value)
            message = _safe_failure_message(exc, base_url)
        except Exception:
            message = "The PostgreSQL migration rehearsal could not start."
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"code": "postgres_rehearsal_failed", "message": message},
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "backend": "postgresql",
                "cases": [asdict(result) for result in results],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
