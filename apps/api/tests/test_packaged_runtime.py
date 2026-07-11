from __future__ import annotations

import os
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

from app import packaged_runtime
from app.packaged_runtime import (
    MigrationSafetyError,
    RuntimePaths,
    SchemaStatus,
    fingerprint_schema,
    initialize_runtime,
    inspect_schema,
    load_runtime_config,
    migrate_database,
    packaged_alembic_config,
    resolve_runtime_paths,
    stamp_inspected_schema,
)

API_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_paths_follow_platform_conventions_and_explicit_overrides(tmp_path) -> None:
    home = tmp_path / "home"

    mac = resolve_runtime_paths(environ={}, system="Darwin", home=home)
    assert mac == RuntimePaths(
        data_dir=home / "Library/Application Support/TaskSignal",
        config_file=home / "Library/Application Support/TaskSignal/config.env",
        database_file=home / "Library/Application Support/TaskSignal/tasksignal.db",
    )

    linux = resolve_runtime_paths(
        environ={
            "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
            "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
        },
        system="Linux",
        home=home,
    )
    assert linux == RuntimePaths(
        data_dir=tmp_path / "xdg-data/TaskSignal",
        config_file=tmp_path / "xdg-config/TaskSignal/config.env",
        database_file=tmp_path / "xdg-data/TaskSignal/tasksignal.db",
    )

    overridden = resolve_runtime_paths(
        environ={
            "TASKSIGNAL_DATA_DIR": str(tmp_path / "custom data"),
            "TASKSIGNAL_CONFIG_FILE": str(tmp_path / "private/config.env"),
        },
        system="Linux",
        home=home,
    )
    assert overridden == RuntimePaths(
        data_dir=tmp_path / "custom data",
        config_file=tmp_path / "private/config.env",
        database_file=tmp_path / "custom data/tasksignal.db",
    )


def test_default_runtime_paths_come_from_platformdirs(tmp_path, monkeypatch) -> None:
    class FakePlatformDirs:
        def __init__(self, appname, *, appauthor, ensure_exists) -> None:
            assert (appname, appauthor, ensure_exists) == ("TaskSignal", False, False)
            self.user_data_dir = str(tmp_path / "platform-data")
            self.user_config_dir = str(tmp_path / "platform-config")

    monkeypatch.setattr(packaged_runtime, "PlatformDirs", FakePlatformDirs)
    monkeypatch.delenv("TASKSIGNAL_DATA_DIR", raising=False)
    monkeypatch.delenv("TASKSIGNAL_CONFIG_FILE", raising=False)

    paths = resolve_runtime_paths()

    assert paths == RuntimePaths(
        data_dir=tmp_path / "platform-data",
        config_file=tmp_path / "platform-config/config.env",
        database_file=tmp_path / "platform-data/tasksignal.db",
    )


def test_init_is_idempotent_and_returns_no_generated_secret_values(tmp_path) -> None:
    paths = RuntimePaths(
        data_dir=tmp_path / "data",
        config_file=tmp_path / "config/config.env",
        database_file=tmp_path / "data/tasksignal.db",
    )

    created = initialize_runtime(paths=paths, environ={})
    first_bytes = paths.config_file.read_bytes()
    initialized = dotenv_values(paths.config_file)

    assert created.config_created is True
    assert created.paths == paths
    assert "secret" not in vars(created)
    assert all(
        value not in repr(created)
        for key, value in initialized.items()
        if key != "DATABASE_URL" and value
    )
    assert stat.S_IMODE(paths.config_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(paths.data_dir.stat().st_mode) & 0o077 == 0
    assert initialized["DATABASE_URL"] == f"sqlite:///{paths.database_file}"
    assert len(initialized["AUTHOR_HASH_SALT"] or "") >= 32
    assert len(initialized["DEMO_RESET_TOKEN"] or "") >= 32
    assert len(initialized["OPERATOR_SCAN_TOKEN"] or "") >= 32

    repeated = initialize_runtime(paths=paths, environ={})

    assert repeated.config_created is False
    assert paths.config_file.read_bytes() == first_bytes
    assert stat.S_IMODE(paths.config_file.stat().st_mode) == 0o600


def test_init_rejects_a_symlinked_secret_config(tmp_path) -> None:
    target = tmp_path / "target.env"
    target.write_text("DO_NOT_TOUCH=true\n", encoding="utf-8")
    config_file = tmp_path / "config.env"
    config_file.symlink_to(target)
    paths = RuntimePaths(tmp_path / "data", config_file, tmp_path / "data/tasksignal.db")

    with pytest.raises(packaged_runtime.PackagedRuntimeError) as error:
        initialize_runtime(paths=paths, environ={})

    assert error.value.code == "unsafe_config_file"
    assert target.read_text(encoding="utf-8") == "DO_NOT_TOUCH=true\n"

    with pytest.raises(packaged_runtime.PackagedRuntimeError) as load_error:
        load_runtime_config(paths=paths, environ={})
    assert load_error.value.code == "unsafe_config_file"


def test_environment_overrides_secret_config_values(tmp_path) -> None:
    paths = RuntimePaths(
        data_dir=tmp_path / "data",
        config_file=tmp_path / "config.env",
        database_file=tmp_path / "data/tasksignal.db",
    )
    initialize_runtime(paths=paths, environ={})
    file_values = dotenv_values(paths.config_file)
    override_url = f"sqlite:///{tmp_path / 'override.db'}"

    loaded = load_runtime_config(
        paths=paths,
        environ={
            "DATABASE_URL": override_url,
            "OPERATOR_SCAN_TOKEN": "environment-operator-token",
        },
    )

    assert loaded.database_url == override_url
    assert loaded.operator_scan_token == "environment-operator-token"
    assert loaded.author_hash_salt == file_values["AUTHOR_HASH_SALT"]
    assert loaded.demo_reset_token == file_values["DEMO_RESET_TOKEN"]
    assert loaded.as_environment()["AUTO_CREATE_TABLES"] == "false"


def test_existing_runtime_directories_are_validated_and_tightened(tmp_path) -> None:
    data_dir = tmp_path / "TaskSignal"
    data_dir.mkdir(mode=0o755)
    data_dir.chmod(0o755)
    paths = RuntimePaths(
        data_dir=data_dir,
        config_file=data_dir / "config.env",
        database_file=data_dir / "tasksignal.db",
    )

    initialize_runtime(paths=paths, environ={})

    assert stat.S_IMODE(data_dir.stat().st_mode) == 0o700


def test_nondedicated_shared_config_directory_must_already_be_private(tmp_path) -> None:
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir(mode=0o755)
    shared_dir.chmod(0o755)
    paths = RuntimePaths(
        data_dir=tmp_path / "TaskSignal",
        config_file=shared_dir / "tasksignal.env",
        database_file=tmp_path / "TaskSignal/tasksignal.db",
    )

    with pytest.raises(packaged_runtime.PackagedRuntimeError) as error:
        initialize_runtime(paths=paths, environ={})

    assert error.value.code == "unsafe_runtime_directory"
    assert stat.S_IMODE(shared_dir.stat().st_mode) == 0o755


def test_packaged_migration_resources_contain_the_complete_revision_graph() -> None:
    packaged_versions = API_ROOT / "app/migrations/versions"
    packaged_files = sorted(
        path.name for path in packaged_versions.glob("*.py") if path.name != "__init__.py"
    )
    assert packaged_files == [
        "0001_initial_schema.py",
        "0002_research_projects.py",
        "0003_project_scheduling.py",
        "0004_local_workspace_settings.py",
        "0005_scan_outcomes.py",
        "0006_decision_workbench.py",
        "0007_discourse_sources.py",
        "0007_opportunity_threads.py",
        "0007_research_memory.py",
        "0008_build_packets.py",
        "0009_agent_sessions_audit.py",
    ]

    config = packaged_alembic_config("sqlite:///:memory:")
    assert Path(config.get_main_option("script_location")) == API_ROOT / "app/migrations"
    assert "script_location = app/migrations" in (API_ROOT / "alembic.ini").read_text(
        encoding="utf-8"
    )
    assert not (API_ROOT / "alembic").exists()


def test_packaged_alembic_env_honors_an_injected_locked_connection(tmp_path) -> None:
    database_file = tmp_path / "connection.db"
    engine = create_engine(f"sqlite:///{database_file}")
    invalid_url = f"sqlite:///{tmp_path / 'missing-parent/database.db'}"
    config = packaged_alembic_config(invalid_url)

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001_initial_schema")

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0001_initial_schema"
        )
    engine.dispose()


def test_inspection_of_missing_sqlite_is_empty_and_does_not_create_a_file(tmp_path) -> None:
    database_file = tmp_path / "missing.db"

    status = inspect_schema(f"sqlite:///{database_file}")

    assert status.state == "empty"
    assert status.current_revision is None
    assert not database_file.exists()


def test_sqlite_migration_uses_packaged_head_and_creates_consistent_backup(tmp_path) -> None:
    database_file = tmp_path / "tasksignal.db"
    database_url = f"sqlite:///{database_file}"
    command.upgrade(packaged_alembic_config(database_url), "0006_decision_workbench")
    before = inspect_schema(database_url)
    assert before.state == "stale"
    assert before.current_revision == "0006_decision_workbench"
    assert before.head_revision == "0009_agent_sessions_audit"

    migrated = migrate_database(database_url)

    assert migrated.migrated is True
    assert migrated.status.state == "current"
    assert migrated.backup_path is not None
    assert migrated.backup_path.parent == database_file.parent
    assert migrated.backup_path.name.startswith("tasksignal.db.backup-")
    assert migrated.backup_path.is_file()

    backup_status = inspect_schema(f"sqlite:///{migrated.backup_path}")
    assert backup_status.current_revision == "0006_decision_workbench"
    assert backup_status.state == "stale"


def test_new_sqlite_database_migrates_without_a_meaningless_backup(tmp_path) -> None:
    database_file = tmp_path / "new.db"
    database_url = f"sqlite:///{database_file}"

    migrated = migrate_database(database_url)

    assert migrated.migrated is True
    assert migrated.backup_path is None
    assert migrated.status == SchemaStatus(
        backend="sqlite",
        current_revision="0009_agent_sessions_audit",
        head_revision="0009_agent_sessions_audit",
        state="current",
    )


def test_nonempty_unversioned_sqlite_requires_explicit_fingerprint_and_stamp(tmp_path) -> None:
    database_file = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database_file}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE legacy_items (id INTEGER PRIMARY KEY, body TEXT)"))
    engine.dispose()

    assert inspect_schema(database_url).state == "unversioned"
    with pytest.raises(MigrationSafetyError) as migration_error:
        migrate_database(database_url)
    assert migration_error.value.code == "legacy_unversioned_schema"

    fingerprint = fingerprint_schema(database_url)
    assert fingerprint.backend == "sqlite"
    assert fingerprint.table_names == ("legacy_items",)
    assert fingerprint.object_names == ("table:legacy_items",)
    assert len(fingerprint.sha256) == 64

    with pytest.raises(MigrationSafetyError) as acknowledgement_error:
        stamp_inspected_schema(
            database_url,
            revision="0006_decision_workbench",
            expected_fingerprint=fingerprint.sha256,
            acknowledge_schema_matches_revision=False,
        )
    assert acknowledgement_error.value.code == "explicit_schema_acknowledgement_required"

    with pytest.raises(MigrationSafetyError) as changed_error:
        stamp_inspected_schema(
            database_url,
            revision="0006_decision_workbench",
            expected_fingerprint="0" * 64,
            acknowledge_schema_matches_revision=True,
        )
    assert changed_error.value.code == "schema_fingerprint_mismatch"

    stamped = stamp_inspected_schema(
        database_url,
        revision="0006_decision_workbench",
        expected_fingerprint=fingerprint.sha256,
        acknowledge_schema_matches_revision=True,
    )
    assert stamped.status.current_revision == "0006_decision_workbench"
    assert stamped.status.state == "stale"
    assert stamped.backup_path is not None
    assert stat.S_IMODE(stamped.backup_path.stat().st_mode) == 0o600
    assert fingerprint_schema(f"sqlite:///{stamped.backup_path}").sha256 == fingerprint.sha256


def test_unknown_sqlite_revision_is_reported_and_never_overwritten(tmp_path) -> None:
    database_file = tmp_path / "unknown.db"
    database_url = f"sqlite:///{database_file}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('foreign_revision')"))
    engine.dispose()

    status = inspect_schema(database_url)
    assert status.state == "unknown"

    with pytest.raises(MigrationSafetyError) as error:
        migrate_database(database_url)

    assert error.value.code == "unknown_schema_revision"
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "foreign_revision"
        )
    engine.dispose()


def test_empty_schema_is_distinct_from_nonempty_unversioned_schema(tmp_path) -> None:
    empty_file = tmp_path / "empty.db"
    sqlite3_engine = create_engine(f"sqlite:///{empty_file}")
    sqlite3_engine.connect().close()
    sqlite3_engine.dispose()
    assert inspect_schema(f"sqlite:///{empty_file}").state == "empty"

    nonempty_file = tmp_path / "nonempty.db"
    sqlite3_engine = create_engine(f"sqlite:///{nonempty_file}")
    with sqlite3_engine.begin() as connection:
        connection.execute(text("CREATE TABLE external_table (id INTEGER PRIMARY KEY)"))
    sqlite3_engine.dispose()
    assert inspect_schema(f"sqlite:///{nonempty_file}").state == "unversioned"


def test_view_only_sqlite_is_unversioned_and_view_changes_affect_fingerprint(tmp_path) -> None:
    database_file = tmp_path / "view-only.db"
    database_url = f"sqlite:///{database_file}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE VIEW external_view AS SELECT 1 AS value"))
    engine.dispose()

    assert inspect_schema(database_url).state == "unversioned"
    with pytest.raises(MigrationSafetyError) as error:
        migrate_database(database_url)
    assert error.value.code == "legacy_unversioned_schema"

    before = fingerprint_schema(database_url)
    assert before.table_names == ()
    assert before.object_names == ("view:external_view",)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP VIEW external_view"))
        connection.execute(text("CREATE VIEW external_view AS SELECT 2 AS value"))
    engine.dispose()

    after = fingerprint_schema(database_url)
    assert after.object_names == before.object_names
    assert after.sha256 != before.sha256


def test_postgresql_empty_schema_is_eligible_but_nonempty_unversioned_is_not() -> None:
    _, script, head = packaged_runtime._packaged_graph(
        "postgresql+psycopg://example.invalid/tasksignal"
    )
    empty = packaged_runtime._schema_status(
        backend="postgresql",
        current_heads=(),
        table_names=set(),
        script=script,
        head=head,
    )
    assert empty.state == "empty"
    packaged_runtime._validate_automatic_migration(empty)

    view_only = packaged_runtime._schema_status(
        backend="postgresql",
        current_heads=(),
        table_names=set(),
        schema_object_names={"relation:v:external_view"},
        script=script,
        head=head,
    )
    assert view_only.state == "unversioned"

    nonempty = packaged_runtime._schema_status(
        backend="postgresql",
        current_heads=(),
        table_names={"external_table"},
        script=script,
        head=head,
    )
    assert nonempty.state == "unversioned"
    with pytest.raises(MigrationSafetyError) as error:
        packaged_runtime._validate_automatic_migration(nonempty)
    assert error.value.code == "postgresql_unversioned_schema"


def test_postgresql_migration_lock_is_transaction_scoped_and_bounded() -> None:
    class RecordingConnection:
        def __init__(self) -> None:
            self.statements: list[str] = []

        def exec_driver_sql(self, statement: str) -> None:
            self.statements.append(statement)

    connection = RecordingConnection()

    packaged_runtime._acquire_migration_lock(connection, backend="postgresql")  # type: ignore[arg-type]

    assert connection.statements == [
        "SET LOCAL lock_timeout = '5s'",
        f"SELECT pg_advisory_xact_lock({packaged_runtime._MIGRATION_LOCK_ID})",
    ]


def test_backup_reservation_does_not_follow_a_colliding_symlink(tmp_path, monkeypatch) -> None:
    source = tmp_path / "tasksignal.db"
    source.touch()
    fixed = datetime(2026, 7, 11, 12, 34, 56, 123456, tzinfo=UTC)

    class FrozenDateTime:
        @classmethod
        def now(cls, timezone):
            assert timezone is UTC
            return fixed

    monkeypatch.setattr(packaged_runtime, "datetime", FrozenDateTime)
    first_candidate = tmp_path / "tasksignal.db.backup-20260711T123456123456Z"
    symlink_target = tmp_path / "must-not-touch"
    symlink_target.write_text("safe", encoding="utf-8")
    first_candidate.symlink_to(symlink_target)

    reserved, descriptor = packaged_runtime._reserve_backup_file(source)
    try:
        assert reserved.name == "tasksignal.db.backup-20260711T123456123456Z-1"
        assert stat.S_IMODE(os.fstat(descriptor).st_mode) == 0o600
        assert symlink_target.read_text(encoding="utf-8") == "safe"
    finally:
        os.close(descriptor)
        reserved.unlink()


@pytest.mark.parametrize(
    ("state", "revision", "error_code"),
    [
        ("unversioned", None, "postgresql_unversioned_schema"),
        ("unknown", "foreign_revision", "postgresql_unknown_schema"),
    ],
)
def test_postgresql_unversioned_or_unknown_schema_requires_explicit_inspection(
    monkeypatch,
    state: str,
    revision: str | None,
    error_code: str,
) -> None:
    database_url = "postgresql+psycopg://user:secret@db.example/tasksignal"
    monkeypatch.setattr(
        packaged_runtime,
        "inspect_schema",
        lambda _database_url: SchemaStatus(
            backend="postgresql",
            current_revision=revision,
            head_revision="0009_agent_sessions_audit",
            state=state,
        ),
    )
    upgrade_called = False

    def unexpected_upgrade(*_args, **_kwargs) -> None:
        nonlocal upgrade_called
        upgrade_called = True

    monkeypatch.setattr(packaged_runtime.command, "upgrade", unexpected_upgrade)

    with pytest.raises(MigrationSafetyError) as error:
        migrate_database(database_url)

    assert error.value.code == error_code
    assert "secret" not in str(error.value)
    assert upgrade_called is False


def test_missing_runtime_config_has_a_structured_error(tmp_path) -> None:
    paths = RuntimePaths(
        data_dir=tmp_path / "data",
        config_file=tmp_path / "missing.env",
        database_file=tmp_path / "data/tasksignal.db",
    )

    with pytest.raises(packaged_runtime.PackagedRuntimeError) as error:
        load_runtime_config(paths=paths, environ={})

    assert error.value.code == "not_initialized"
    assert os.fspath(paths.config_file) in str(error.value)


def test_packaged_cli_ignores_an_unrelated_hostile_cwd_dotenv(tmp_path) -> None:
    hostile_cwd = tmp_path / "unrelated-project"
    hostile_cwd.mkdir()
    hostile_cwd.joinpath(".env").write_text(
        "REQUIRE_OPERATOR_TOKEN_FOR_ALL_API=definitely-not-a-bool\n"
        "OPENAI_API_KEY=HOSTILE-CWD-SECRET-MUST-NOT-LEAK\n",
        encoding="utf-8",
    )
    runtime_root = tmp_path / "runtime"
    environment = os.environ.copy()
    for key in (
        "DATABASE_URL",
        "AUTHOR_HASH_SALT",
        "DEMO_RESET_TOKEN",
        "OPERATOR_SCAN_TOKEN",
        "TASKSIGNAL_PACKAGED_MODE",
    ):
        environment.pop(key, None)
    environment["PYTHONPATH"] = str(API_ROOT)
    environment["TASKSIGNAL_DATA_DIR"] = str(runtime_root / "data")
    environment["TASKSIGNAL_CONFIG_FILE"] = str(runtime_root / "data/config.env")

    outputs: list[str] = []
    for command_name in ("init", "migrate"):
        completed = subprocess.run(
            [sys.executable, "-m", "app.cli", "--json", command_name],
            cwd=hostile_cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        outputs.append(completed.stdout + completed.stderr)

    assert "HOSTILE-CWD-SECRET-MUST-NOT-LEAK" not in "".join(outputs)
    assert inspect_schema(f"sqlite:///{runtime_root / 'data/tasksignal.db'}").state == "current"
