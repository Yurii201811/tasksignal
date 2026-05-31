import os

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import all_models  # noqa: F401


def create_app() -> FastAPI:
    app = FastAPI(
        title="TaskSignal API",
        description="AI-assisted problem discovery engine with local fixture demo mode.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.on_event("startup")
    def create_tables() -> None:
        if settings.auto_create_tables:
            Base.metadata.create_all(bind=engine)

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "llm_provider": settings.llm_provider,
            "embedding_model": settings.embedding_model,
            "fixture_mode": True,
        }

    return app


app = create_app()
