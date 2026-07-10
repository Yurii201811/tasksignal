import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_default_runtime_is_loopback_only_and_reproducible() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    api_config = (ROOT / "apps/api/app/core/config.py").read_text(encoding="utf-8")
    dockerignore_path = ROOT / "apps/web/.dockerignore"

    assert '"127.0.0.1:5432:5432"' in compose
    assert '"127.0.0.1:8000:8000"' in compose
    assert '"127.0.0.1:3000:3000"' in compose
    assert package["scripts"]["dev"] == "next dev"
    assert package["scripts"]["start"] == "next start -H 0.0.0.0"
    assert "COPY package.json package-lock.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "- run: npm ci" in ci
    assert "- run: npm audit --audit-level=moderate" in ci
    assert 'reddit_user_agent: str = "tasksignal-local-demo/0.2"' in api_config
    assert dockerignore_path.exists()
    dockerignore = dockerignore_path.read_text(encoding="utf-8").splitlines()
    assert "node_modules" in dockerignore
    assert ".next" in dockerignore
