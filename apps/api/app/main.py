import os
import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

from fastapi import FastAPI, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.core.security import secret_text_matches
from app.core.version import TASKSIGNAL_VERSION
from app.db.base import Base
from app.db.session import engine, ensure_sqlite_schema_compatibility
from app.models import all_models  # noqa: F401

CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOWED_HEADERS = ["Content-Type", "X-Operator-Scan-Token", "Authorization", "Accept"]
RATE_LIMITED_POST_PATHS = frozenset({"/scans", "/process/demo", "/search/semantic"})
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_MAX_RATE_LIMIT_BUCKETS = 4096


def _is_local_environment() -> bool:
    if hasattr(settings, "is_local_environment"):
        return bool(settings.is_local_environment)
    return str(getattr(settings, "environment", "local")).strip().lower() == "local"


def _effective_rate_limit_per_minute() -> int:
    if hasattr(settings, "effective_rate_limit_per_minute"):
        return int(settings.effective_rate_limit_per_minute)
    configured = getattr(settings, "rate_limit_requests_per_minute", None)
    if configured is not None:
        return int(configured)
    return 0 if _is_local_environment() else 60


def _normalize_rate_limit_path(path: str) -> str | None:
    if path.startswith("/api/v1/"):
        suffix = path[len("/api/v1") :]
    elif path.startswith("/api/"):
        suffix = path[len("/api") :]
    else:
        return None
    normalized = suffix.rstrip("/")
    return normalized if normalized in RATE_LIMITED_POST_PATHS else None


def cors_allowed_origins() -> list[str]:
    origins = [
        origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
    ]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]


def operator_token_matches(supplied_token: str | None, configured_token: str) -> bool:
    """Compare tokens without failing on malformed or non-ASCII header values."""
    return secret_text_matches(supplied_token, configured_token)


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
        version=TASKSIGNAL_VERSION,
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

    rate_limit_buckets: dict[tuple[str, str], deque[float]] = {}

    @app.middleware("http")
    async def enforce_high_load_rate_limit(request: Request, call_next):
        limit = _effective_rate_limit_per_minute()
        if limit > 0 and request.method.upper() == "POST":
            route_key = _normalize_rate_limit_path(request.url.path)
            if route_key is not None:
                now = time.monotonic()
                cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
                if len(rate_limit_buckets) >= _MAX_RATE_LIMIT_BUCKETS:
                    stale_keys = [
                        key
                        for key, hits in rate_limit_buckets.items()
                        if not hits or hits[-1] <= cutoff
                    ]
                    for key in stale_keys:
                        del rate_limit_buckets[key]
                client_host = request.client.host if request.client else "unknown"
                bucket = rate_limit_buckets.setdefault((client_host, route_key), deque())
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()
                if len(bucket) >= limit:
                    retry_after = max(1, int(_RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])) + 1)
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Rate limit exceeded for this endpoint. Retry later."},
                        headers={"Retry-After": str(retry_after)},
                    )
                bucket.append(now)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins(),
        allow_credentials=True,
        allow_methods=CORS_ALLOWED_METHODS,
        allow_headers=CORS_ALLOWED_HEADERS,
    )
    app.include_router(router, prefix="/api/v1")
    app.include_router(router, prefix="/api", include_in_schema=False)

    @app.get("/health")
    def health(
        x_operator_scan_token: str | None = Header(default=None),
    ) -> dict[str, object]:
        if not _is_local_environment() and not operator_token_matches(
            x_operator_scan_token, settings.operator_scan_token
        ):
            return {"status": "ok"}
        return {
            "status": "ok",
            "llm_provider": settings.llm_provider,
            "embedding_model": settings.embedding_model,
            "fixture_mode": True,
        }

    return app


app = create_app()
