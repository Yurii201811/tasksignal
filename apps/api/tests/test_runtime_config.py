import json
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def compose_port_mappings(compose: str) -> list[str]:
    mappings: list[str] = []
    ports_indent: int | None = None
    for line in compose.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped == "ports:":
            ports_indent = indent
            continue
        if ports_indent is None:
            continue
        if stripped and indent <= ports_indent:
            ports_indent = None
            continue
        if stripped.startswith("-"):
            mappings.append(stripped.removeprefix("-").strip().strip("\"'"))
    return mappings


def git_ignores(path: str) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", path],
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode in {0, 1}
    return completed.returncode == 0


def test_project_root_resolution_supports_native_and_container_layouts(tmp_path) -> None:
    from app.core import config

    native_config = ROOT / "apps/api/app/core/config.py"
    assert config.resolve_project_root(native_config) == ROOT

    container_root = tmp_path / "app"
    container_config = container_root / "app/core/config.py"
    container_config.parent.mkdir(parents=True)
    container_config.touch()
    (container_root / "data/fixtures").mkdir(parents=True)

    assert config.resolve_project_root(container_config) == container_root

    packaged_fixtures = config.resolve_fixture_dir(tmp_path / "installed-package")
    assert (packaged_fixtures / "hn_sample.json").is_file()


def test_database_url_normalization_selects_psycopg3() -> None:
    from app.core.config import Settings, normalize_database_url

    assert normalize_database_url("postgres://user:pass@db:5432/tasksignal") == (
        "postgresql+psycopg://user:pass@db:5432/tasksignal"
    )
    assert normalize_database_url("postgresql://user:pass@db:5432/tasksignal") == (
        "postgresql+psycopg://user:pass@db:5432/tasksignal"
    )
    assert (
        normalize_database_url("postgresql+psycopg://user:pass@db:5432/tasksignal")
        == "postgresql+psycopg://user:pass@db:5432/tasksignal"
    )
    assert normalize_database_url("sqlite:///./tasksignal.db") == "sqlite:///./tasksignal.db"
    assert Settings(database_url="postgresql://user:pass@db:5432/tasksignal").database_url == (
        "postgresql+psycopg://user:pass@db:5432/tasksignal"
    )


def test_cloud_runtime_keeps_local_ml_optional() -> None:
    project = tomllib.loads((ROOT / "apps/api/pyproject.toml").read_text(encoding="utf-8"))
    core_dependencies = project["project"]["dependencies"]
    ml_dependencies = project["project"]["optional-dependencies"]["ml"]
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert not any(
        dependency.startswith("sentence-transformers") for dependency in core_dependencies
    )
    assert not any(dependency.startswith("scikit-learn") for dependency in core_dependencies)
    assert any(dependency.startswith("sentence-transformers") for dependency in ml_dependencies)
    assert any(dependency.startswith("scikit-learn") for dependency in ml_dependencies)
    assert "setup-ml:" in makefile
    assert "--extra dev --extra ml --locked" in makefile


def test_hosted_deployment_manifests_are_safe_and_reproducible() -> None:
    render_config = (ROOT / "render.yaml").read_text(encoding="utf-8")
    api_vercel_config = json.loads((ROOT / "apps/api/vercel.json").read_text(encoding="utf-8"))
    vercel_config = json.loads((ROOT / "apps/web/vercel.json").read_text(encoding="utf-8"))
    api_project = tomllib.loads((ROOT / "apps/api/pyproject.toml").read_text(encoding="utf-8"))
    api_vercelignore = (ROOT / "apps/api/.vercelignore").read_text(encoding="utf-8")
    prepare_script = (ROOT / "scripts/prepare_vercel_api.sh").read_text(encoding="utf-8")
    deployment = (ROOT / "docs/deployment.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "name: tasksignal-api-yurii201811" in render_config
    assert "runtime: python" in render_config
    assert "plan: free" in render_config
    assert "region: frankfurt" in render_config
    assert "autoDeployTrigger: checksPass" in render_config
    assert "rootDir:" not in render_config
    assert "pip install uv==0.9.26" in render_config
    assert "uv sync --project apps/api --locked --no-dev" in render_config
    start = render_config.index(".venv/bin/alembic upgrade head")
    server = render_config.index(".venv/bin/uvicorn app.main:app")
    assert start < server
    assert '--port "$PORT"' in render_config
    assert "healthCheckPath: /health" in render_config
    assert "- apps/api/**" in render_config
    assert "- data/fixtures/**" in render_config
    assert "key: OPERATOR_SCAN_TOKEN\n        sync: false" in render_config
    assert 'key: REQUIRE_OPERATOR_TOKEN_FOR_ALL_API\n        value: "true"' in render_config
    assert 'key: REQUIRE_OPERATOR_TOKEN_FOR_WRITES\n        value: "true"' in render_config
    assert (
        "key: CORS_ALLOWED_ORIGINS\n        value: https://tasksignal-yurii201811.vercel.app"
        in render_config
    )
    assert "name: tasksignal-db" in render_config
    assert 'postgresMajorVersion: "16"' in render_config
    assert "ipAllowList: []" in render_config

    assert api_vercel_config["$schema"] == "https://openapi.vercel.sh/vercel.json"
    assert api_vercel_config["framework"] == "fastapi"
    assert api_vercel_config["regions"] == ["iad1"]
    api_function = api_vercel_config["functions"]["app/main.py"]
    assert api_function["maxDuration"] == 60
    assert api_function["includeFiles"] == "data/fixtures/**"
    assert api_function["excludeFiles"] == "{tests/**,**/__pycache__/**}"
    assert api_project["tool"]["vercel"]["entrypoint"] == "app.main:app"
    assert (ROOT / "apps/api/.python-version").read_text(encoding="utf-8").strip() == "3.12"
    assert ".env*" in api_vercelignore
    assert "tests" in api_vercelignore
    assert 'SOURCE_DIR="$ROOT_DIR/data/fixtures"' in prepare_script
    assert 'TARGET_DIR="$ROOT_DIR/.vercel-api"' in prepare_script
    assert "--exclude '__pycache__/' --exclude '*.pyc'" in prepare_script
    assert '"$API_DIR/app/" "$TARGET_DIR/app/"' in prepare_script
    assert 'rsync -a --delete "$SOURCE_DIR/" "$TARGET_DIR/data/fixtures/"' in prepare_script
    assert "for file in pyproject.toml uv.lock vercel.json .python-version .vercelignore" in (
        prepare_script
    )
    assert 'rsync -a "$API_DIR/.vercel/project.json"' in prepare_script
    assert "AUTO_CREATE_TABLES=false" in deployment
    assert "AUTHOR_HASH_SALT=<long random value>" in deployment

    assert vercel_config["$schema"] == "https://openapi.vercel.sh/vercel.json"
    assert vercel_config["framework"] == "nextjs"
    assert vercel_config["installCommand"] == "npm ci"
    assert vercel_config["buildCommand"] == "npm run build"
    assert "env" not in vercel_config
    assert "build" not in vercel_config
    assert "REQUIRE_OPERATOR_TOKEN_FOR_ALL_API=false" in env_example
    assert "REQUIRE_OPERATOR_TOKEN_FOR_WRITES=false" in env_example


def test_vercel_api_bundle_contains_only_runtime_inputs() -> None:
    completed = subprocess.run(
        [str(ROOT / "scripts/prepare_vercel_api.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    bundle = ROOT / ".vercel-api"
    allowed_top_level = {
        ".python-version",
        ".vercel",
        ".vercelignore",
        "app",
        "data",
        "pyproject.toml",
        "uv.lock",
        "vercel.json",
    }
    assert {path.name for path in bundle.iterdir()} <= allowed_top_level
    assert not list(bundle.glob(".env*"))
    assert not (bundle / "tests").exists()
    assert not (bundle / "test_tasksignal.db").exists()

    source_app_files = {
        path.relative_to(ROOT / "apps/api/app")
        for path in (ROOT / "apps/api/app").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    bundled_app_files = {
        path.relative_to(bundle / "app")
        for path in (bundle / "app").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert bundled_app_files == source_app_files

    source_fixture_files = {
        path.relative_to(ROOT / "data/fixtures")
        for path in (ROOT / "data/fixtures").rglob("*")
        if path.is_file()
    }
    bundled_fixture_files = {
        path.relative_to(bundle / "data/fixtures")
        for path in (bundle / "data/fixtures").rglob("*")
        if path.is_file()
    }
    assert bundled_fixture_files == source_fixture_files


def test_default_runtime_is_loopback_only_and_reproducible() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    web_dockerfile = (ROOT / "apps/web/Dockerfile").read_text(encoding="utf-8")
    api_dockerfile = (ROOT / "apps/api/Dockerfile").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    api_config = (ROOT / "apps/api/app/core/config.py").read_text(encoding="utf-8")
    deployment = (ROOT / "docs/deployment.md").read_text(encoding="utf-8")
    web_dockerignore_path = ROOT / "apps/web/.dockerignore"
    api_dockerignore_path = ROOT / "apps/api/.dockerignore"

    port_mappings = compose_port_mappings(compose)
    assert port_mappings == [
        "127.0.0.1:5432:5432",
        "127.0.0.1:8000:8000",
        "127.0.0.1:3000:3000",
    ]
    unsafe_mappings = {
        "5432:5432",
        "8000:8000",
        "3000:3000",
        "0.0.0.0:5432:5432",
        "0.0.0.0:8000:8000",
        "0.0.0.0:3000:3000",
    }
    assert unsafe_mappings.isdisjoint(port_mappings)
    assert package["scripts"]["dev"] == "next dev -H 127.0.0.1"
    assert package["scripts"]["start"] == "next start -H 0.0.0.0"
    assert "COPY package.json package-lock.json ./" in web_dockerfile
    assert "RUN npm ci" in web_dockerfile
    assert "- run: npm ci" in ci
    assert "- run: npm audit --audit-level=moderate" in ci
    assert 'reddit_user_agent: str = "tasksignal-local-demo/0.2"' in api_config
    assert web_dockerignore_path.exists()
    web_dockerignore = web_dockerignore_path.read_text(encoding="utf-8").splitlines()
    assert "node_modules" in web_dockerignore
    assert ".next" in web_dockerignore
    assert git_ignores("apps/web/.env.local")
    assert git_ignores(".env.local")
    assert not git_ignores(".env.example")
    assert not git_ignores("apps/web/.env.example")
    assert web_dockerignore[-2:] == [".env*", "!.env.example"]

    assert api_dockerignore_path.exists()
    api_dockerignore = api_dockerignore_path.read_text(encoding="utf-8").splitlines()
    assert {
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "*.pyc",
        "*.db",
        "*.db-shm",
        "*.db-wal",
        "*.egg-info",
        "build",
        "dist",
        ".DS_Store",
    }.issubset(api_dockerignore)
    assert api_dockerignore[-2:] == [".env*", "!.env.example"]
    assert "uv.lock" not in api_dockerignore
    assert "app" not in api_dockerignore
    assert "alembic" not in api_dockerignore

    assert "ghcr.io/astral-sh/uv:0.9.26" in api_dockerfile
    assert "COPY pyproject.toml uv.lock ./" in api_dockerfile
    assert "COPY app ./app" in api_dockerfile
    assert "COPY alembic ./alembic" not in api_dockerfile
    assert 'ENV PATH="/app/.venv/bin:$PATH"' in api_dockerfile
    assert "uv sync --locked --no-dev --no-install-project" in api_dockerfile
    assert "uv sync --locked --no-dev" in api_dockerfile
    assert "pip install" not in api_dockerfile

    backend_ci = ci.split("  frontend:", maxsplit=1)[0]
    assert "uses: astral-sh/setup-uv@v7" in backend_ci
    assert 'UV_VERSION: "0.9.26"' in ci
    assert "version: ${{ env.UV_VERSION }}" in backend_ci
    assert "working-directory: apps/api" not in backend_ci
    assert "- run: uv sync --project apps/api --extra dev --locked" in backend_ci
    assert (
        "- run: uv run --project apps/api --extra dev --locked ruff check "
        "apps/api/app apps/api/tests" in backend_ci
    )
    assert (
        "- run: uv run --project apps/api --extra dev --locked pytest apps/api/tests" in backend_ci
    )
    assert "pip install" not in backend_ci

    compose_database_url = "postgresql+psycopg://tasksignal:tasksignal@db:5432/tasksignal"
    assert f"DATABASE_URL: {compose_database_url}" in compose
    assert "migrate:\n\tdocker compose run --rm --build api alembic upgrade head" in makefile
    assert "migrate-native:\n\tcd apps/api && .venv/bin/alembic upgrade head" in makefile
    assert "`make migrate` runs Alembic inside the Compose API service" in deployment
    assert "`make migrate-native`" in deployment
    assert "apps/api/.env" in deployment
