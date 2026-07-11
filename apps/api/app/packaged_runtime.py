"""Safe initialization and schema management for the packaged local runtime.

The module intentionally avoids importing TaskSignal's process-global settings and
engine.  CLI startup can therefore initialize private configuration, inspect schema
compatibility, and migrate before importing the API application.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
import sqlite3
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from dotenv import dotenv_values
from platformdirs import PlatformDirs
from sqlalchemy import Connection, create_engine
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

SchemaState = Literal["current", "stale", "empty", "unversioned", "unknown"]

_CONFIG_KEYS = (
    "DATABASE_URL",
    "AUTHOR_HASH_SALT",
    "DEMO_RESET_TOKEN",
    "OPERATOR_SCAN_TOKEN",
)
_MIGRATION_LOCK_ID = 8_348_353_697_130_785_947
_SQLITE_SCHEMA_OBJECTS_SQL = """
SELECT type, name,
       CASE WHEN tbl_name = name THEN '' ELSE COALESCE(tbl_name, '') END,
       COALESCE(sql, '')
FROM sqlite_master
WHERE name NOT LIKE 'sqlite_%'
  AND NOT (type = 'table' AND name = 'alembic_version')
ORDER BY type, name
"""
_POSTGRESQL_SCHEMA_OBJECTS_SQL = """
WITH target_namespace AS (
    SELECT oid
    FROM pg_namespace
    WHERE nspname = current_schema()
), relation_objects AS (
    SELECT
        'relation:' || c.relkind::text AS kind,
        c.relname::text AS name,
        ''::text AS identity,
        CASE
            WHEN c.relkind IN ('v', 'm') THEN pg_get_viewdef(c.oid, true)
            WHEN c.relkind IN ('i', 'I') THEN pg_get_indexdef(c.oid)
            WHEN c.relkind = 'S' THEN COALESCE((
                SELECT concat_ws(':', s.seqstart, s.seqincrement, s.seqmax,
                                      s.seqmin, s.seqcache, s.seqcycle)
                FROM pg_sequence AS s
                WHERE s.seqrelid = c.oid
            ), '')
            WHEN c.relkind = 'c' THEN COALESCE((
                SELECT string_agg(
                    a.attname || ':' || format_type(a.atttypid, a.atttypmod),
                    ',' ORDER BY a.attnum
                )
                FROM pg_attribute AS a
                WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            ), '')
            ELSE ''
        END::text AS definition
    FROM pg_class AS c
    WHERE c.relnamespace = (SELECT oid FROM target_namespace)
      AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f', 'c', 'i', 'I')
      AND c.relname <> 'alembic_version'
      AND NOT (
          c.relkind IN ('i', 'I')
          AND EXISTS (
              SELECT 1
              FROM pg_index AS ix
              JOIN pg_class AS parent ON parent.oid = ix.indrelid
              WHERE ix.indexrelid = c.oid AND parent.relname = 'alembic_version'
          )
      )
), type_objects AS (
    SELECT
        'type:' || t.typtype::text AS kind,
        t.typname::text AS name,
        ''::text AS identity,
        CASE
            WHEN t.typtype = 'e' THEN COALESCE((
                SELECT string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder)
                FROM pg_enum AS e
                WHERE e.enumtypid = t.oid
            ), '')
            WHEN t.typtype = 'd' THEN concat_ws(
                ':', format_type(t.typbasetype, t.typtypmod), t.typnotnull,
                COALESCE(pg_get_expr(t.typdefaultbin, 0), t.typdefault, '')
            )
            WHEN t.typtype IN ('r', 'm') THEN COALESCE((
                SELECT format_type(r.rngsubtype, NULL)
                FROM pg_range AS r
                WHERE r.rngtypid = t.oid OR r.rngmultitypid = t.oid
            ), '')
            ELSE format_type(t.oid, NULL)
        END::text AS definition
    FROM pg_type AS t
    LEFT JOIN pg_class AS related_class ON related_class.reltype = t.oid
    WHERE t.typnamespace = (SELECT oid FROM target_namespace)
      AND related_class.oid IS NULL
      AND t.typtype IN ('c', 'd', 'e', 'r', 'm')
), routine_objects AS (
    SELECT
        'routine:' || p.prokind::text AS kind,
        p.proname::text AS name,
        pg_get_function_identity_arguments(p.oid)::text AS identity,
        CASE
            WHEN p.prokind IN ('f', 'p') THEN pg_get_functiondef(p.oid)
            ELSE concat_ws(':', p.prorettype, p.prosrc)
        END::text AS definition
    FROM pg_proc AS p
    WHERE p.pronamespace = (SELECT oid FROM target_namespace)
), trigger_objects AS (
    SELECT
        'trigger'::text AS kind,
        t.tgname::text AS name,
        c.relname::text AS identity,
        pg_get_triggerdef(t.oid, true)::text AS definition
    FROM pg_trigger AS t
    JOIN pg_class AS c ON c.oid = t.tgrelid
    WHERE c.relnamespace = (SELECT oid FROM target_namespace)
      AND NOT t.tgisinternal
), extension_objects AS (
    SELECT
        'extension'::text AS kind,
        e.extname::text AS name,
        ''::text AS identity,
        e.extversion::text AS definition
    FROM pg_extension AS e
    WHERE e.extnamespace = (SELECT oid FROM target_namespace)
)
SELECT kind, name, identity, definition FROM relation_objects
UNION ALL
SELECT kind, name, identity, definition FROM type_objects
UNION ALL
SELECT kind, name, identity, definition FROM routine_objects
UNION ALL
SELECT kind, name, identity, definition FROM trigger_objects
UNION ALL
SELECT kind, name, identity, definition FROM extension_objects
ORDER BY 1, 2, 3
"""


class PackagedRuntimeError(RuntimeError):
    """A credential-safe structured failure suitable for CLI rendering."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class MigrationSafetyError(PackagedRuntimeError):
    """A mutation refused because the schema cannot be changed automatically."""


@dataclass(frozen=True)
class RuntimePaths:
    data_dir: Path
    config_file: Path
    database_file: Path


@dataclass(frozen=True)
class InitResult:
    """Secret-free result of an idempotent initialization."""

    paths: RuntimePaths
    config_created: bool


@dataclass(frozen=True)
class RuntimeConfig:
    database_url: str
    author_hash_salt: str
    demo_reset_token: str
    operator_scan_token: str

    def as_environment(self) -> dict[str, str]:
        """Return the environment consumed by the existing API runtime."""
        return {
            "DATABASE_URL": self.database_url,
            "AUTHOR_HASH_SALT": self.author_hash_salt,
            "DEMO_RESET_TOKEN": self.demo_reset_token,
            "OPERATOR_SCAN_TOKEN": self.operator_scan_token,
            "AUTO_CREATE_TABLES": "false",
        }


@dataclass(frozen=True)
class SchemaStatus:
    backend: str
    current_revision: str | None
    head_revision: str
    state: SchemaState


@dataclass(frozen=True)
class MigrationResult:
    status: SchemaStatus
    migrated: bool
    backup_path: Path | None


@dataclass(frozen=True)
class SchemaFingerprint:
    """Deterministic metadata-only fingerprint; it never reads table rows."""

    backend: str
    table_names: tuple[str, ...]
    object_names: tuple[str, ...]
    sha256: str


@dataclass(frozen=True)
class StampResult:
    status: SchemaStatus
    fingerprint: SchemaFingerprint
    backup_path: Path | None


def _expanded_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().absolute()


def resolve_runtime_paths(
    *,
    environ: Mapping[str, str] | None = None,
    system: str | None = None,
    home: Path | None = None,
) -> RuntimePaths:
    """Resolve macOS/Linux defaults and explicit TaskSignal path overrides."""
    environment = os.environ if environ is None else environ
    operating_system = platform.system() if system is None else system
    user_home = Path.home() if home is None else home
    data_override = environment.get("TASKSIGNAL_DATA_DIR")
    config_override = environment.get("TASKSIGNAL_CONFIG_FILE")
    platform_paths = PlatformDirs("TaskSignal", appauthor=False, ensure_exists=False)

    if operating_system not in {"Darwin", "Linux"}:
        raise PackagedRuntimeError(
            "unsupported_platform",
            "Packaged mode supports macOS and Linux; Windows is supported through WSL only.",
        )
    if system is None and home is None and environ is None:
        default_data_dir = Path(platform_paths.user_data_dir)
        default_config_dir = Path(platform_paths.user_config_dir)
    elif operating_system == "Darwin":
        default_data_dir = user_home / "Library/Application Support/TaskSignal"
        default_config_dir = user_home / "Library/Application Support/TaskSignal"
    else:
        data_base = _expanded_path(environment.get("XDG_DATA_HOME", user_home / ".local/share"))
        config_base = _expanded_path(environment.get("XDG_CONFIG_HOME", user_home / ".config"))
        default_data_dir = data_base / "TaskSignal"
        default_config_dir = config_base / "TaskSignal"

    default_config_file = default_config_dir / "config.env"
    data_dir = _expanded_path(data_override) if data_override else default_data_dir.absolute()
    config_file = (
        _expanded_path(config_override) if config_override else default_config_file.absolute()
    )
    return RuntimePaths(data_dir, config_file, data_dir / "tasksignal.db")


def _directory_open_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _ensure_private_directory(path: Path, *, tighten_existing: bool) -> None:
    existed = path.exists() or path.is_symlink()
    if not existed:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        descriptor = os.open(path, _directory_open_flags())
    except OSError as exc:
        raise PackagedRuntimeError(
            "unsafe_runtime_directory",
            f"Refusing to use unsafe runtime directory: {path}",
        ) from exc
    try:
        file_status = os.fstat(descriptor)
        if not stat.S_ISDIR(file_status.st_mode):
            raise PackagedRuntimeError(
                "unsafe_runtime_directory",
                f"Refusing to use non-directory runtime path: {path}",
            )
        if hasattr(os, "getuid") and file_status.st_uid != os.getuid():
            raise PackagedRuntimeError(
                "unsafe_runtime_directory",
                f"Refusing to use a runtime directory owned by another user: {path}",
            )
        if not existed or tighten_existing:
            os.fchmod(descriptor, 0o700)
        elif stat.S_IMODE(file_status.st_mode) & 0o077:
            raise PackagedRuntimeError(
                "unsafe_runtime_directory",
                f"Runtime config directory must not be accessible to other users: {path}",
            )
    finally:
        os.close(descriptor)


def _config_open_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _open_private_config(path: Path) -> int:
    try:
        descriptor = os.open(path, _config_open_flags())
    except OSError as exc:
        if isinstance(exc, FileNotFoundError):
            raise FileNotFoundError(path) from None
        raise PackagedRuntimeError(
            "unsafe_config_file",
            f"Refusing to use unsafe secret config file: {path}",
        ) from exc
    try:
        descriptor_status = os.fstat(descriptor)
        path_status = path.lstat()
        if (
            not stat.S_ISREG(descriptor_status.st_mode)
            or stat.S_ISLNK(path_status.st_mode)
            or (descriptor_status.st_dev, descriptor_status.st_ino)
            != (path_status.st_dev, path_status.st_ino)
        ):
            raise PackagedRuntimeError(
                "unsafe_config_file",
                f"Refusing to use non-regular secret config file: {path}",
            )
        if hasattr(os, "getuid") and descriptor_status.st_uid != os.getuid():
            raise PackagedRuntimeError(
                "unsafe_config_file",
                f"Refusing to use a secret config owned by another user: {path}",
            )
        os.fchmod(descriptor, 0o600)
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _validate_existing_config(path: Path) -> bool:
    try:
        descriptor = _open_private_config(path)
    except FileNotFoundError:
        return False
    os.close(descriptor)
    return True


def _render_initial_config(paths: RuntimePaths) -> bytes:
    values = {
        "DATABASE_URL": f"sqlite:///{paths.database_file}",
        "AUTHOR_HASH_SALT": secrets.token_urlsafe(32),
        "DEMO_RESET_TOKEN": secrets.token_urlsafe(32),
        "OPERATOR_SCAN_TOKEN": secrets.token_urlsafe(32),
    }
    return (
        "\n".join(f"{key}={json.dumps(value)}" for key, value in values.items()) + "\n"
    ).encode()


def _same_file(descriptor: int, path: Path) -> bool:
    try:
        descriptor_status = os.fstat(descriptor)
        path_status = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISREG(path_status.st_mode) and (
        descriptor_status.st_dev,
        descriptor_status.st_ino,
    ) == (path_status.st_dev, path_status.st_ino)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, _directory_open_flags())
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def initialize_runtime(
    *,
    paths: RuntimePaths | None = None,
    environ: Mapping[str, str] | None = None,
) -> InitResult:
    """Create private directories and a 0600 config without returning secret values."""
    resolved = resolve_runtime_paths(environ=environ) if paths is None else paths
    _ensure_private_directory(resolved.data_dir, tighten_existing=True)
    config_parent_is_dedicated = (
        resolved.config_file.parent == resolved.data_dir
        or resolved.config_file.parent.name.casefold() == "tasksignal"
    )
    _ensure_private_directory(
        resolved.config_file.parent,
        tighten_existing=config_parent_is_dedicated,
    )
    if _validate_existing_config(resolved.config_file):
        return InitResult(resolved, config_created=False)

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(resolved.config_file, flags, 0o600)
    except FileExistsError:
        if _validate_existing_config(resolved.config_file):
            return InitResult(resolved, config_created=False)
        raise
    except OSError as exc:
        raise PackagedRuntimeError(
            "config_create_failed",
            f"Could not create private TaskSignal config at {resolved.config_file}.",
        ) from exc

    try:
        os.fchmod(descriptor, 0o600)
        payload = _render_initial_config(resolved)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
        if not _same_file(descriptor, resolved.config_file):
            raise PackagedRuntimeError(
                "unsafe_config_file",
                "The TaskSignal config path changed while it was being initialized.",
            )
    except Exception as exc:
        if _same_file(descriptor, resolved.config_file):
            resolved.config_file.unlink(missing_ok=True)
        if isinstance(exc, PackagedRuntimeError):
            raise
        raise PackagedRuntimeError(
            "config_write_failed",
            f"Could not write private TaskSignal config at {resolved.config_file}.",
        ) from exc
    finally:
        os.close(descriptor)
    _fsync_directory(resolved.config_file.parent)
    return InitResult(resolved, config_created=True)


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def load_runtime_config(
    *,
    paths: RuntimePaths | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    """Read the private config by descriptor and apply environment precedence."""
    environment = os.environ if environ is None else environ
    resolved = resolve_runtime_paths(environ=environ) if paths is None else paths
    try:
        descriptor = _open_private_config(resolved.config_file)
    except FileNotFoundError as exc:
        raise PackagedRuntimeError(
            "not_initialized",
            f"TaskSignal is not initialized; config file is missing: {resolved.config_file}",
        ) from exc
    with os.fdopen(descriptor, encoding="utf-8") as config_stream:
        loaded = dotenv_values(stream=config_stream)
    values = {
        key: environment[key] if key in environment else loaded.get(key) for key in _CONFIG_KEYS
    }
    missing = [key for key, value in values.items() if not isinstance(value, str) or not value]
    if missing:
        raise PackagedRuntimeError(
            "invalid_config",
            "TaskSignal config is missing required settings: " + ", ".join(sorted(missing)),
        )
    return RuntimeConfig(
        database_url=_normalize_database_url(str(values["DATABASE_URL"])),
        author_hash_salt=str(values["AUTHOR_HASH_SALT"]),
        demo_reset_token=str(values["DEMO_RESET_TOKEN"]),
        operator_scan_token=str(values["OPERATOR_SCAN_TOKEN"]),
    )


def _migration_resource_path() -> Path:
    path = Path(str(resources.files("app.migrations")))
    if not path.is_dir():
        raise PackagedRuntimeError(
            "migration_resources_unavailable",
            "Packaged Alembic migration resources are unavailable.",
        )
    return path


def packaged_alembic_config(database_url: str) -> Config:
    """Build an Alembic config targeting migration resources installed in the wheel."""
    config = Config()
    config.set_main_option("script_location", os.fspath(_migration_resource_path()))
    config.set_main_option(
        "sqlalchemy.url", _normalize_database_url(database_url).replace("%", "%%")
    )
    return config


def _backend_name(database_url: str) -> str:
    try:
        backend = make_url(_normalize_database_url(database_url)).get_backend_name()
    except Exception as exc:
        raise PackagedRuntimeError(
            "invalid_database_url",
            "The configured database URL is invalid.",
        ) from exc
    if backend not in {"sqlite", "postgresql"}:
        raise PackagedRuntimeError(
            "unsupported_database",
            f"Packaged mode does not support the {backend} database backend.",
        )
    return backend


def _packaged_graph(database_url: str) -> tuple[Config, ScriptDirectory, str]:
    config = packaged_alembic_config(database_url)
    script = ScriptDirectory.from_config(config)
    try:
        head = script.get_current_head()
    except Exception as exc:
        raise PackagedRuntimeError(
            "invalid_migration_graph",
            "Packaged migrations do not have exactly one head revision.",
        ) from exc
    if head is None:
        raise PackagedRuntimeError(
            "invalid_migration_graph",
            "Packaged migrations have no head revision.",
        )
    return config, script, head


def _object_record(
    kind: object,
    name: object,
    identity: object,
    definition: object,
) -> dict[str, str]:
    return {
        "kind": str(kind or ""),
        "name": str(name or ""),
        "identity": str(identity or ""),
        "definition": str(definition or ""),
    }


def _sqlite_schema_objects(connection: sqlite3.Connection) -> list[dict[str, str]]:
    return [_object_record(*row) for row in connection.execute(_SQLITE_SCHEMA_OBJECTS_SQL)]


def _connection_schema_objects(
    connection: Connection,
    *,
    backend: str,
) -> list[dict[str, str]]:
    statement = (
        _SQLITE_SCHEMA_OBJECTS_SQL if backend == "sqlite" else _POSTGRESQL_SCHEMA_OBJECTS_SQL
    )
    return [_object_record(*row) for row in connection.exec_driver_sql(statement)]


def _schema_object_names(objects: list[dict[str, str]]) -> tuple[str, ...]:
    return tuple(
        f"{item['kind']}:{item['name']}" + (f"({item['identity']})" if item["identity"] else "")
        for item in objects
    )


def _schema_status(
    *,
    backend: str,
    current_heads: tuple[str, ...],
    table_names: set[str],
    schema_object_names: set[str] | None = None,
    script: ScriptDirectory,
    head: str,
) -> SchemaStatus:
    application_objects = (
        table_names - {"alembic_version"} if schema_object_names is None else schema_object_names
    )
    if not current_heads:
        state: SchemaState = "empty" if not application_objects else "unversioned"
        return SchemaStatus(backend, None, head, state)
    if len(current_heads) != 1:
        return SchemaStatus(backend, ",".join(sorted(current_heads)), head, "unknown")
    current = current_heads[0]
    if current == head:
        return SchemaStatus(backend, current, head, "current")
    try:
        recognized = script.get_revision(current) is not None
    except Exception:
        recognized = False
    return SchemaStatus(backend, current, head, "stale" if recognized else "unknown")


def _sqlite_database_file(database_url: str) -> Path:
    database = make_url(database_url).database
    if not database or database == ":memory:" or database.startswith("file:"):
        raise MigrationSafetyError(
            "sqlite_file_required",
            "Packaged schema management requires a file-backed SQLite database.",
        )
    return _expanded_path(database)


def _validate_sqlite_file(path: Path) -> bool:
    try:
        file_status = path.lstat()
    except FileNotFoundError:
        return False
    if path.is_symlink() or not stat.S_ISREG(file_status.st_mode):
        raise MigrationSafetyError(
            "unsafe_sqlite_file",
            f"Refusing to use non-regular SQLite database file: {path}",
        )
    return True


def _sqlite_uri(path: Path, *, mode: str) -> str:
    return f"file:{quote(os.fspath(path), safe='/')}?mode={mode}&nofollow=1"


def _inspect_sqlite(
    database_url: str,
    *,
    script: ScriptDirectory,
    head: str,
) -> SchemaStatus:
    database_file = _sqlite_database_file(database_url)
    if not _validate_sqlite_file(database_file):
        return SchemaStatus("sqlite", None, head, "empty")
    try:
        with sqlite3.connect(_sqlite_uri(database_file, mode="ro"), uri=True) as connection:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            current_heads = (
                tuple(
                    row[0]
                    for row in connection.execute(
                        "SELECT version_num FROM alembic_version ORDER BY version_num"
                    )
                )
                if "alembic_version" in table_names
                else ()
            )
            schema_objects = _sqlite_schema_objects(connection)
    except sqlite3.Error as exc:
        raise PackagedRuntimeError(
            "database_unavailable",
            "Could not inspect the configured TaskSignal SQLite database.",
        ) from exc
    return _schema_status(
        backend="sqlite",
        current_heads=current_heads,
        table_names=table_names,
        schema_object_names=set(_schema_object_names(schema_objects)),
        script=script,
        head=head,
    )


def _inspect_connection(
    connection: Connection,
    *,
    backend: str,
    script: ScriptDirectory,
    head: str,
) -> SchemaStatus:
    current_heads = tuple(MigrationContext.configure(connection).get_current_heads())
    table_names = set(sqlalchemy_inspect(connection).get_table_names())
    schema_objects = _connection_schema_objects(connection, backend=backend)
    return _schema_status(
        backend=backend,
        current_heads=current_heads,
        table_names=table_names,
        schema_object_names=set(_schema_object_names(schema_objects)),
        script=script,
        head=head,
    )


def inspect_schema(database_url: str) -> SchemaStatus:
    """Inspect packaged schema compatibility without creating a missing SQLite file."""
    normalized_url = _normalize_database_url(database_url)
    backend = _backend_name(normalized_url)
    _, script, head = _packaged_graph(normalized_url)
    if backend == "sqlite":
        return _inspect_sqlite(normalized_url, script=script, head=head)

    engine = create_engine(normalized_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            return _inspect_connection(
                connection,
                backend=backend,
                script=script,
                head=head,
            )
    except SQLAlchemyError as exc:
        raise PackagedRuntimeError(
            "database_unavailable",
            "Could not inspect the configured TaskSignal database.",
        ) from exc
    finally:
        engine.dispose()


def _secure_sqlite_database_file(path: Path) -> int:
    """Open and retain an identity guard for a 0600 SQLite file."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise MigrationSafetyError(
            "unsafe_sqlite_file",
            f"Could not securely open SQLite database file: {path}",
        ) from exc
    try:
        file_status = os.fstat(descriptor)
        if not stat.S_ISREG(file_status.st_mode) or not _same_file(descriptor, path):
            raise MigrationSafetyError(
                "unsafe_sqlite_file",
                f"Refusing to use unsafe SQLite database file: {path}",
            )
        if hasattr(os, "getuid") and file_status.st_uid != os.getuid():
            raise MigrationSafetyError(
                "unsafe_sqlite_file",
                f"Refusing to use a SQLite database owned by another user: {path}",
            )
        os.fchmod(descriptor, 0o600)
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _assert_sqlite_identity(descriptor: int, path: Path) -> None:
    if not _same_file(descriptor, path):
        raise MigrationSafetyError(
            "sqlite_path_changed",
            "The SQLite database path changed while schema management was in progress.",
        )


def _acquire_migration_lock(connection: Connection, *, backend: str) -> None:
    if backend == "sqlite":
        connection.exec_driver_sql("PRAGMA busy_timeout = 5000")
        if connection.in_transaction():
            connection.commit()
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        return
    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
    connection.exec_driver_sql(f"SELECT pg_advisory_xact_lock({_MIGRATION_LOCK_ID})")


@contextmanager
def _locked_connection(database_url: str, *, backend: str) -> Iterator[Connection]:
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        connection = engine.connect()
    except SQLAlchemyError as exc:
        engine.dispose()
        raise PackagedRuntimeError(
            "database_unavailable",
            "Could not open the configured TaskSignal database.",
        ) from exc
    try:
        _acquire_migration_lock(connection, backend=backend)
        yield connection
        if connection.in_transaction():
            connection.commit()
    except Exception:
        if connection.in_transaction():
            connection.rollback()
        raise
    finally:
        connection.close()
        engine.dispose()


def _reserve_backup_file(source: Path) -> tuple[Path, int]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    suffix = 0
    while True:
        tail = "" if suffix == 0 else f"-{suffix}"
        candidate = source.with_name(f"{source.name}.backup-{timestamp}{tail}")
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(candidate, flags, 0o600)
        except FileExistsError:
            suffix += 1
            continue
        except OSError as exc:
            raise PackagedRuntimeError(
                "sqlite_backup_failed",
                f"Could not reserve a migration backup beside {source.name}.",
            ) from exc
        try:
            file_status = os.fstat(descriptor)
            if not stat.S_ISREG(file_status.st_mode):
                raise PackagedRuntimeError(
                    "sqlite_backup_failed",
                    "Could not reserve a regular SQLite backup file.",
                )
            os.fchmod(descriptor, 0o600)
        except Exception:
            os.close(descriptor)
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return candidate, descriptor


def _sqlite_backup(source: Path, *, source_descriptor: int) -> Path:
    """Create a consistent, exclusive 0600 SQLite backup while a writer lock is held."""
    _assert_sqlite_identity(source_descriptor, source)
    backup_path, descriptor = _reserve_backup_file(source)
    source_connection: sqlite3.Connection | None = None
    backup_connection: sqlite3.Connection | None = None
    try:
        source_connection = sqlite3.connect(_sqlite_uri(source, mode="ro"), uri=True)
        _assert_sqlite_identity(source_descriptor, source)
        backup_connection = sqlite3.connect(_sqlite_uri(backup_path, mode="rw"), uri=True)
        if not _same_file(descriptor, backup_path):
            raise PackagedRuntimeError(
                "sqlite_backup_failed",
                "The SQLite backup path changed during creation.",
            )
        source_connection.backup(backup_connection)
        _assert_sqlite_identity(source_descriptor, source)
        backup_connection.commit()
        backup_connection.close()
        backup_connection = None
        os.fsync(descriptor)
        if not _same_file(descriptor, backup_path):
            raise PackagedRuntimeError(
                "sqlite_backup_failed",
                "The SQLite backup path changed before it was finalized.",
            )
        _fsync_directory(backup_path.parent)
    except (sqlite3.Error, OSError, PackagedRuntimeError) as exc:
        if _same_file(descriptor, backup_path):
            backup_path.unlink(missing_ok=True)
        if isinstance(exc, PackagedRuntimeError):
            raise
        raise PackagedRuntimeError(
            "sqlite_backup_failed",
            f"Could not create a migration backup beside {source.name}.",
        ) from exc
    finally:
        if backup_connection is not None:
            backup_connection.close()
        if source_connection is not None:
            source_connection.close()
        os.close(descriptor)
    return backup_path


def _validate_automatic_migration(status: SchemaStatus) -> None:
    if status.state == "unversioned":
        code = (
            "postgresql_unversioned_schema"
            if status.backend == "postgresql"
            else "legacy_unversioned_schema"
        )
        raise MigrationSafetyError(
            code,
            "Refusing to migrate a nonempty unversioned schema automatically; inspect its fingerprint and stamp it explicitly.",
        )
    if status.state == "unknown":
        code = (
            "postgresql_unknown_schema"
            if status.backend == "postgresql"
            else "unknown_schema_revision"
        )
        raise MigrationSafetyError(
            code,
            "Refusing to migrate a database with an unknown Alembic revision.",
        )


def migrate_database(database_url: str) -> MigrationResult:
    """Upgrade empty/stale schemas; never infer lineage for nonempty unversioned data."""
    normalized_url = _normalize_database_url(database_url)
    backend = _backend_name(normalized_url)
    preflight = inspect_schema(normalized_url)
    if preflight.state == "current":
        return MigrationResult(preflight, migrated=False, backup_path=None)
    _validate_automatic_migration(preflight)

    sqlite_file: Path | None = None
    sqlite_descriptor: int | None = None
    if backend == "sqlite":
        sqlite_file = _sqlite_database_file(normalized_url)
        sqlite_descriptor = _secure_sqlite_database_file(sqlite_file)

    config, script, head = _packaged_graph(normalized_url)
    backup_path: Path | None = None
    try:
        with _locked_connection(normalized_url, backend=backend) as connection:
            if sqlite_file is not None and sqlite_descriptor is not None:
                _assert_sqlite_identity(sqlite_descriptor, sqlite_file)
            locked_status = _inspect_connection(
                connection,
                backend=backend,
                script=script,
                head=head,
            )
            if locked_status.state == "current":
                return MigrationResult(locked_status, migrated=False, backup_path=None)
            _validate_automatic_migration(locked_status)
            if (
                sqlite_file is not None
                and sqlite_descriptor is not None
                and locked_status.state == "stale"
            ):
                backup_path = _sqlite_backup(
                    sqlite_file,
                    source_descriptor=sqlite_descriptor,
                )
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            if sqlite_file is not None and sqlite_descriptor is not None:
                _assert_sqlite_identity(sqlite_descriptor, sqlite_file)
            migrated_status = _inspect_connection(
                connection,
                backend=backend,
                script=script,
                head=head,
            )
            if migrated_status.state != "current":
                raise PackagedRuntimeError(
                    "migration_incomplete",
                    "TaskSignal migration did not reach the packaged schema head.",
                )
    except PackagedRuntimeError:
        raise
    except Exception as exc:
        raise PackagedRuntimeError(
            "migration_failed",
            "TaskSignal database migration failed; no automatic recovery was attempted.",
        ) from exc
    finally:
        if sqlite_descriptor is not None:
            os.close(sqlite_descriptor)
    return MigrationResult(migrated_status, migrated=True, backup_path=backup_path)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value, key=str)]
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _fingerprint_connection(connection: Connection, *, backend: str) -> SchemaFingerprint:
    inspector = sqlalchemy_inspect(connection)
    schema_objects = _connection_schema_objects(connection, backend=backend)
    object_names = _schema_object_names(schema_objects)
    table_names = tuple(
        sorted(name for name in inspector.get_table_names() if name != "alembic_version")
    )
    tables: list[dict[str, Any]] = []
    for table_name in table_names:
        columns = [
            {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column.get("nullable"),
                "default": _json_safe(column.get("default")),
                "primary_key": column.get("primary_key", 0),
            }
            for column in inspector.get_columns(table_name)
        ]
        tables.append(
            {
                "name": table_name,
                "columns": columns,
                "primary_key": _json_safe(inspector.get_pk_constraint(table_name)),
                "foreign_keys": _json_safe(inspector.get_foreign_keys(table_name)),
                "indexes": _json_safe(inspector.get_indexes(table_name)),
                "unique_constraints": _json_safe(inspector.get_unique_constraints(table_name)),
                "check_constraints": _json_safe(inspector.get_check_constraints(table_name)),
            }
        )
    payload = json.dumps(
        {"backend": backend, "objects": schema_objects, "tables": tables},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return SchemaFingerprint(
        backend,
        table_names,
        object_names,
        hashlib.sha256(payload).hexdigest(),
    )


def fingerprint_schema(database_url: str) -> SchemaFingerprint:
    """Fingerprint schema metadata only, for an explicit operator stamping decision."""
    normalized_url = _normalize_database_url(database_url)
    backend = _backend_name(normalized_url)
    status = inspect_schema(normalized_url)
    if status.state == "empty":
        raise MigrationSafetyError(
            "empty_schema_has_no_fingerprint",
            "An empty database can be migrated directly and does not need stamping.",
        )
    if backend == "sqlite":
        _validate_sqlite_file(_sqlite_database_file(normalized_url))
    engine = create_engine(normalized_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            return _fingerprint_connection(connection, backend=backend)
    except SQLAlchemyError as exc:
        raise PackagedRuntimeError(
            "database_unavailable",
            "Could not fingerprint the configured TaskSignal database schema.",
        ) from exc
    finally:
        engine.dispose()


def stamp_inspected_schema(
    database_url: str,
    *,
    revision: str,
    expected_fingerprint: str,
    acknowledge_schema_matches_revision: bool,
) -> StampResult:
    """Stamp a stable inspected schema only after an explicit operator assertion.

    This does not infer a revision from timestamps or table contents.  The caller must
    inspect the schema, choose the revision, supply the exact metadata fingerprint,
    and explicitly acknowledge that the schema matches that revision.
    """
    if not acknowledge_schema_matches_revision:
        raise MigrationSafetyError(
            "explicit_schema_acknowledgement_required",
            "Stamping requires explicit acknowledgement that the inspected schema matches the requested revision.",
        )
    normalized_url = _normalize_database_url(database_url)
    backend = _backend_name(normalized_url)
    preflight = inspect_schema(normalized_url)
    if preflight.state != "unversioned":
        raise MigrationSafetyError(
            "schema_not_unversioned",
            "Only a nonempty unversioned schema can use the explicit fingerprint/stamp path.",
        )
    config, script, head = _packaged_graph(normalized_url)
    try:
        if script.get_revision(revision) is None:
            raise LookupError(revision)
    except Exception as exc:
        raise MigrationSafetyError(
            "unknown_stamp_revision",
            "The requested stamp revision is not present in the packaged migration graph.",
        ) from exc

    sqlite_file: Path | None = None
    sqlite_descriptor: int | None = None
    if backend == "sqlite":
        sqlite_file = _sqlite_database_file(normalized_url)
        sqlite_descriptor = _secure_sqlite_database_file(sqlite_file)
    backup_path: Path | None = None
    try:
        with _locked_connection(normalized_url, backend=backend) as connection:
            if sqlite_file is not None and sqlite_descriptor is not None:
                _assert_sqlite_identity(sqlite_descriptor, sqlite_file)
            locked_status = _inspect_connection(
                connection,
                backend=backend,
                script=script,
                head=head,
            )
            if locked_status.state != "unversioned":
                raise MigrationSafetyError(
                    "schema_changed_during_inspection",
                    "The schema state changed before the stamp lock was acquired.",
                )
            fingerprint = _fingerprint_connection(connection, backend=backend)
            if not secrets.compare_digest(fingerprint.sha256, expected_fingerprint):
                raise MigrationSafetyError(
                    "schema_fingerprint_mismatch",
                    "The schema fingerprint changed or does not match the inspected value.",
                )
            if sqlite_file is not None and sqlite_descriptor is not None:
                backup_path = _sqlite_backup(
                    sqlite_file,
                    source_descriptor=sqlite_descriptor,
                )
            config.attributes["connection"] = connection
            command.stamp(config, revision)
            if sqlite_file is not None and sqlite_descriptor is not None:
                _assert_sqlite_identity(sqlite_descriptor, sqlite_file)
            stamped_status = _inspect_connection(
                connection,
                backend=backend,
                script=script,
                head=head,
            )
            if stamped_status.current_revision != revision:
                raise PackagedRuntimeError(
                    "stamp_incomplete",
                    "The explicit schema stamp did not persist the requested revision.",
                )
    except PackagedRuntimeError:
        raise
    except Exception as exc:
        raise PackagedRuntimeError(
            "stamp_failed",
            "The explicit schema stamp failed; no revision was inferred automatically.",
        ) from exc
    finally:
        if sqlite_descriptor is not None:
            os.close(sqlite_descriptor)
    return StampResult(stamped_status, fingerprint, backup_path)
