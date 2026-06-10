#!/usr/bin/env python3
"""Credential-free first-run smoke check for TaskSignal."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
WEB_DIR = ROOT / "apps" / "web"
HOMEBREW_NODE20_BIN = Path("/opt/homebrew/opt/node@20/bin")


class SmokeError(RuntimeError):
    """Raised when a first-run smoke check fails."""


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen
    log_path: Path
    log_handle: object

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.log_handle.close()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def web_env(api_base: str) -> dict[str, str]:
    env = os.environ.copy()
    if HOMEBREW_NODE20_BIN.exists():
        env["PATH"] = f"{HOMEBREW_NODE20_BIN}{os.pathsep}{env.get('PATH', '')}"
    env["NEXT_PUBLIC_API_BASE_URL"] = api_base
    return env


def api_env(database_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "AUTO_CREATE_TABLES": "true",
            "AUTHOR_HASH_SALT": "first-run-smoke-local-only",
            "DATABASE_URL": f"sqlite:///{database_path}",
            "LLM_PROVIDER": "none",
            "PUBLIC_SCAN_SOURCES": "fixture,hackernews",
        }
    )
    return env


def start_process(
    name: str,
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_dir: Path,
) -> ManagedProcess:
    log_path = log_dir / f"{name}.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return ManagedProcess(name=name, process=process, log_path=log_path, log_handle=log_handle)


def request_text(url: str, *, timeout: float = 30) -> str:
    try:
        with urlopen(url, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                raise SmokeError(f"GET {url} failed with HTTP {status}")
            return response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise SmokeError(f"GET {url} could not connect: {exc.reason}") from exc


def wait_for(name: str, check, *, timeout: float, delay: float = 0.5) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            check()
            return
        except Exception as exc:  # noqa: BLE001 - report the last startup failure.
            last_error = exc
            time.sleep(delay)
    detail = f": {last_error}" if last_error else ""
    raise SmokeError(f"{name} did not become ready within {timeout:.0f}s{detail}")


def tail_log(path: Path, *, lines: int = 20) -> str:
    if not path.exists():
        return "log file is missing"
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def assert_condition(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def client_json(client, method: str, path: str, payload: dict | None = None) -> dict | list:
    response = client.request(method, path, json=payload)
    if response.status_code >= 400:
        raise SmokeError(
            f"{method} {path} failed with HTTP {response.status_code}: {response.text}"
        )
    return response.json()


def run_api_checks(database_path: Path) -> dict[str, object]:
    os.environ.update(api_env(database_path))
    sys.path.insert(0, str(API_DIR))

    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient` is deprecated.*",
    )
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        health = client_json(client, "GET", "/health")
        readiness = client_json(client, "GET", "/api/readiness")
        summary = client_json(client, "POST", "/api/process/demo")
        stats = client_json(client, "GET", "/api/stats")
        opportunities = client_json(client, "GET", "/api/opportunities")

        assert_condition(isinstance(health, dict), "Health response was not an object.")
        assert_condition(health.get("status") == "ok", "Health endpoint did not return ok.")

        assert_condition(isinstance(readiness, dict), "Readiness response was not an object.")
        assert_condition(readiness.get("status") == "ready", "Readiness did not report ready.")

        assert_condition(isinstance(summary, dict), "Demo summary response was not an object.")
        assert_condition(
            summary.get("raw_items_loaded", 0) >= 17,
            "Demo loaded too few raw items.",
        )
        assert_condition(
            summary.get("signals_detected", 0) >= 15,
            "Demo detected too few signals.",
        )
        assert_condition(
            summary.get("opportunities_created", 0) >= 5,
            "Demo generated too few opportunities.",
        )

        assert_condition(isinstance(stats, dict), "Stats response was not an object.")
        assert_condition(stats.get("total_items", 0) >= 17, "Stats show too few items.")
        assert_condition(stats.get("opportunities", 0) >= 5, "Stats show too few opportunities.")

        assert_condition(
            isinstance(opportunities, list),
            "Opportunities response was not a list.",
        )
        assert_condition(len(opportunities) >= 5, "Opportunity list contains too few items.")
        first_opportunity = opportunities[0]
        assert_condition(
            isinstance(first_opportunity, dict) and first_opportunity.get("id"),
            "Top opportunity is missing an id.",
        )
        task_pack = client_json(
            client,
            "GET",
            f"/api/opportunities/{first_opportunity['id']}/task-pack.json",
        )
        assert_condition(isinstance(task_pack, dict), "Task-pack response was not an object.")
        assert_condition(
            str(task_pack.get("markdown", "")).startswith("# TaskSignal Codex Task Pack:"),
            "Task-pack markdown was not generated.",
        )
        assert_condition(task_pack.get("evidence_urls"), "Task-pack has no evidence URLs.")

        return {
            "raw_items_loaded": summary["raw_items_loaded"],
            "signals_detected": summary["signals_detected"],
            "opportunities_created": summary["opportunities_created"],
            "top_opportunity": first_opportunity["title"],
        }


def run_dashboard_source_check() -> None:
    route_path = WEB_DIR / "src" / "app" / "dashboard" / "page.tsx"
    feature_path = WEB_DIR / "src" / "features" / "dashboard.tsx"
    assert_condition(route_path.exists(), "Dashboard route file is missing.")
    assert_condition(feature_path.exists(), "Dashboard feature file is missing.")

    route_text = route_path.read_text(encoding="utf-8")
    assert_condition(
        'from "@/features/dashboard"' in route_text,
        "Dashboard route is not wired to the dashboard feature.",
    )


def run_live_web_check(web_base: str) -> None:
    dashboard_html = request_text(f"{web_base}/dashboard")
    assert_condition("<html" in dashboard_html.lower(), "Dashboard route did not return HTML.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a clean TaskSignal first-run smoke check against a temporary database."
    )
    parser.add_argument(
        "--api-timeout",
        type=int,
        default=60,
        help="Reserved for compatibility; API checks run in-process.",
    )
    parser.add_argument(
        "--web-timeout",
        type=int,
        default=90,
        help="Seconds to wait for the Next.js dashboard route.",
    )
    parser.add_argument(
        "--skip-web",
        action="store_true",
        help="Only smoke the API fixture flow and task-pack export.",
    )
    parser.add_argument(
        "--with-web-server",
        action="store_true",
        help="Also start Next.js and request /dashboard. This uses the native Next compiler.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    processes: list[ManagedProcess] = []
    temp_dir = Path(tempfile.mkdtemp(prefix="tasksignal-smoke-"))
    passed = False
    web_port = free_port()
    api_base = "http://127.0.0.1:8000"
    web_base = f"http://127.0.0.1:{web_port}"

    try:
        result = run_api_checks(temp_dir / "tasksignal-smoke.db")
        print("[OK] API fixture endpoints passed with a temporary database", flush=True)
        print(
            "[OK] Fixture flow: "
            f"{result['raw_items_loaded']} raw items, "
            f"{result['signals_detected']} signals, "
            f"{result['opportunities_created']} opportunities",
            flush=True,
        )
        print(f"[OK] Task-pack export: {result['top_opportunity']}", flush=True)

        if not args.skip_web:
            run_dashboard_source_check()
            print("[OK] Dashboard route source is wired", flush=True)

        if args.with_web_server and not args.skip_web:
            next_bin = WEB_DIR / "node_modules" / ".bin" / "next"
            if not next_bin.exists():
                raise SmokeError(
                    "apps/web/node_modules/.bin/next is missing; run npm install in apps/web."
                )
            web = start_process(
                "web",
                [
                    str(next_bin),
                    "dev",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    str(web_port),
                ],
                cwd=WEB_DIR,
                env=web_env(api_base),
                log_dir=temp_dir,
            )
            processes.append(web)

            def check_dashboard() -> None:
                exit_code = web.process.poll()
                if exit_code is not None:
                    raise SmokeError(
                        "Web process exited before the dashboard loaded "
                        f"(exit {exit_code}). Last log lines:\n{tail_log(web.log_path)}"
                    )
                run_live_web_check(web_base)

            wait_for(
                "Web dashboard",
                check_dashboard,
                timeout=args.web_timeout,
            )
            print(f"[OK] Dashboard route loaded at {web_base}/dashboard", flush=True)
        passed = True

    except SmokeError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        for managed in processes:
            print(
                f"[INFO] {managed.name} log: {managed.log_path}",
                file=sys.stderr,
            )
        return 1
    finally:
        for managed in reversed(processes):
            managed.stop()
        if passed:
            shutil.rmtree(temp_dir, ignore_errors=True)

    print("[OK] First-run smoke passed with a temporary database.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
