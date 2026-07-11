import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from secrets import compare_digest

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine, ensure_sqlite_schema_compatibility
from app.models import all_models  # noqa: F401


def cors_allowed_origins() -> list[str]:
    origins = [
        origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
    ]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]


def operator_token_matches(supplied_token: str | None, configured_token: str) -> bool:
    """Compare tokens without failing on malformed or non-ASCII header values."""
    if not supplied_token or not configured_token:
        return False
    return compare_digest(supplied_token.encode(), configured_token.encode())


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_schema_compatibility(engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TaskSignal API",
        description="AI-assisted problem discovery engine with local fixture demo mode.",
        version="0.2.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def protect_hosted_api(request: Request, call_next):
        method = request.method.upper()
        unsafe_method = request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        protect_all_api = (
            settings.require_operator_token_for_all_api
            and request.url.path.startswith("/api/")
            and method != "OPTIONS"
        )
        protect_write = settings.require_operator_token_for_writes and unsafe_method
        if protect_all_api or protect_write:
            supplied_token = request.headers.get("X-Operator-Scan-Token")
            configured_token = settings.operator_scan_token
            if not operator_token_matches(supplied_token, configured_token):
                detail = (
                    "Hosted API access requires a valid X-Operator-Scan-Token."
                    if protect_all_api
                    else "Hosted writes require a valid X-Operator-Scan-Token."
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": detail},
                )
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")
    app.include_router(router, prefix="/api", include_in_schema=False)

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
