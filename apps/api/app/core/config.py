from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def resolve_project_root(config_file: Path) -> Path:
    """Resolve fixture roots across source checkouts and container images."""
    resolved = config_file.resolve()
    ancestors = list(resolved.parents)

    for candidate in ancestors:
        if (candidate / "data/fixtures").is_dir():
            return candidate
        if (candidate / "apps/api/app").is_dir():
            return candidate

    for candidate in ancestors:
        if (candidate / "app").is_dir() and (candidate / "alembic.ini").is_file():
            return candidate

    app_package = next((candidate for candidate in ancestors if candidate.name == "app"), None)
    return app_package.parent if app_package is not None else resolved.parent


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
    reddit_user_agent: str = "tasksignal-local-demo/0.2"
    github_token: str = ""
    stack_exchange_key: str = ""
    demo_reset_token: str = ""
    operator_scan_token: str = ""
    public_scan_sources: str = "fixture,hackernews"
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def project_root(self) -> Path:
        return resolve_project_root(Path(__file__))

    @property
    def fixture_dir(self) -> Path:
        return self.project_root / "data" / "fixtures"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
