import os
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(database_url: str) -> str:
    """Select the installed psycopg3 driver for provider-style Postgres URLs."""
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def resolve_project_root(config_file: Path) -> Path:
    """Resolve fixture roots across source checkouts and container images."""
    resolved = config_file.resolve()
    ancestors = list(resolved.parents)

    for candidate in ancestors:
        if (candidate / "apps/api/app").is_dir():
            return candidate

    for candidate in ancestors:
        if (candidate / "data/fixtures").is_dir():
            return candidate

    for candidate in ancestors:
        if (candidate / "app").is_dir() and (candidate / "alembic.ini").is_file():
            return candidate

    app_package = next((candidate for candidate in ancestors if candidate.name == "app"), None)
    return app_package.parent if app_package is not None else resolved.parent


def resolve_fixture_dir(project_root: Path) -> Path:
    source_fixtures = project_root / "data" / "fixtures"
    if source_fixtures.is_dir():
        return source_fixtures
    return Path(str(files("app.resources.fixtures")))


class Settings(BaseSettings):
    database_url: str = "sqlite:///./tasksignal.db"
    api_base_url: str = "http://localhost:8000"
    llm_provider: str = "none"
    llm_model: str = "gpt-5"
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    author_hash_salt: str = "change-me"
    auto_create_tables: bool = True
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "tasksignal-local-demo/1.0"
    github_token: str = ""
    stack_exchange_key: str = ""
    demo_reset_token: str = ""
    operator_scan_token: str = ""
    require_operator_token_for_all_api: bool = False
    require_operator_token_for_writes: bool = False
    public_scan_sources: str = "fixture,hackernews"
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def select_psycopg3_driver(cls, value: object) -> object:
        return normalize_database_url(value) if isinstance(value, str) else value

    @property
    def project_root(self) -> Path:
        return resolve_project_root(Path(__file__))

    @property
    def fixture_dir(self) -> Path:
        return resolve_fixture_dir(self.project_root)


@lru_cache
def get_settings() -> Settings:
    env_file = None if os.getenv("TASKSIGNAL_PACKAGED_MODE") == "1" else ".env"
    settings_class: Any = Settings
    return settings_class(_env_file=env_file)


settings = get_settings()
