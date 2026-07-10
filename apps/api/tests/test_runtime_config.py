import json
import subprocess
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
            mappings.append(stripped.removeprefix("-").strip().strip('"\''))
    return mappings


def git_ignores(path: str) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", path],
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode in {0, 1}
    return completed.returncode == 0


def test_default_runtime_is_loopback_only_and_reproducible() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    api_config = (ROOT / "apps/api/app/core/config.py").read_text(encoding="utf-8")
    dockerignore_path = ROOT / "apps/web/.dockerignore"

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
    assert "COPY package.json package-lock.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "- run: npm ci" in ci
    assert "- run: npm audit --audit-level=moderate" in ci
    assert 'reddit_user_agent: str = "tasksignal-local-demo/0.2"' in api_config
    assert dockerignore_path.exists()
    dockerignore = dockerignore_path.read_text(encoding="utf-8").splitlines()
    assert "node_modules" in dockerignore
    assert ".next" in dockerignore
    assert git_ignores("apps/web/.env.local")
    assert git_ignores(".env.local")
    assert not git_ignores(".env.example")
    assert not git_ignores("apps/web/.env.example")
    assert dockerignore[-2:] == [".env*", "!.env.example"]
