from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./tasksignal.db"
    api_base_url: str = "http://localhost:8000"
    llm_provider: str = "none"
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    author_hash_salt: str = "change-me"
    auto_create_tables: bool = True
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "tasksignal-local-demo/0.1"
    github_token: str = ""
    stack_exchange_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[4]

    @property
    def fixture_dir(self) -> Path:
        return self.project_root / "data" / "fixtures"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
