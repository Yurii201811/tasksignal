from collections.abc import Generator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

SQLITE_COMPAT_COLUMNS = {
    "scan_jobs": [
        ("signals_detected", "INTEGER NOT NULL DEFAULT 0"),
        ("clusters_created", "INTEGER NOT NULL DEFAULT 0"),
        ("opportunities_created", "INTEGER NOT NULL DEFAULT 0"),
        ("outcome_message", "TEXT"),
    ],
    "research_projects": [
        ("schedule_interval_hours", "INTEGER"),
        ("last_run_at", "DATETIME"),
        ("next_run_at", "DATETIME"),
        ("run_count", "INTEGER NOT NULL DEFAULT 0"),
    ],
}


def ensure_sqlite_schema_compatibility(target_engine: Engine = engine) -> None:
    """Repair local SQLite databases created before newer additive migrations."""
    if target_engine.dialect.name != "sqlite":
        return

    inspector = inspect(target_engine)
    tables = set(inspector.get_table_names())
    with target_engine.begin() as connection:
        for table_name, columns in SQLITE_COMPAT_COLUMNS.items():
            if table_name not in tables:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, column_sql in columns:
                if column_name in existing_columns:
                    continue
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
                )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
