#!/usr/bin/env python3
"""Install and exercise the built TaskSignal wheel outside the source tree."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_command(venv_dir: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    directory = "Scripts" if os.name == "nt" else "bin"
    return venv_dir / directory / f"{name}{suffix}"


def _run(
    command: list[str | Path],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        rendered = " ".join(str(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {rendered}\n"
            f"stdout:\n{completed.stdout[-4000:]}\n"
            f"stderr:\n{completed.stderr[-4000:]}"
        )
    return completed


def _json_cli(
    tasksignal: Path,
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> tuple[dict[str, object], str]:
    completed = _run([tasksignal, "--json", *args], cwd=cwd, env=env)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"tasksignal {' '.join(args)} did not emit one JSON document"
        ) from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError(f"tasksignal {' '.join(args)} returned a failure envelope")
    if set(payload) != {"ok", "data", "error", "meta"}:
        raise RuntimeError(f"tasksignal {' '.join(args)} returned an unstable envelope")
    return payload, completed.stdout + completed.stderr


def _assert_packaged_inventory(python: Path, *, cwd: Path, env: dict[str, str]) -> None:
    code = r"""
from importlib import metadata, resources

distribution = metadata.distribution("tasksignal")
files = {str(path) for path in distribution.files or ()}
required = {
    "app/migrations/env.py",
    "app/resources/fixtures/github_issues_sample.json",
    "app/resources/fixtures/hn_sample.json",
    "app/resources/fixtures/reddit_sample.json",
    "app/resources/fixtures/stackexchange_sample.json",
}
missing = sorted(required - files)
if missing:
    raise SystemExit(f"wheel is missing packaged runtime files: {missing}")
revisions = [path for path in files if path.startswith("app/migrations/versions/") and path.endswith(".py")]
if not revisions:
    raise SystemExit("wheel contains no packaged Alembic revisions")
fixture_root = resources.files("app.resources.fixtures")
if not fixture_root.joinpath("hn_sample.json").is_file():
    raise SystemExit("packaged fixture resources are not readable")
"""
    _run([python, "-c", code], cwd=cwd, env=env)


def _assert_mcp_state(
    python: Path,
    *,
    expected: bool,
    cwd: Path,
    env: dict[str, str],
) -> None:
    code = r"""
import importlib.util
import os

expected = os.environ["TASKSIGNAL_EXPECT_MCP"] == "1"
installed = importlib.util.find_spec("mcp") is not None
if installed != expected:
    raise SystemExit(f"MCP installed={installed}, expected={expected}")
if expected:
    from app.mcp_server import server  # noqa: F401
"""
    check_env = {**env, "TASKSIGNAL_EXPECT_MCP": "1" if expected else "0"}
    _run([python, "-c", code], cwd=cwd, env=check_env)


def smoke_wheel(wheel: Path) -> None:
    wheel = wheel.resolve(strict=True)
    if wheel.suffix != ".whl" or not wheel.is_file():
        raise ValueError(f"expected one wheel file, got: {wheel}")

    with tempfile.TemporaryDirectory(prefix="tasksignal-wheel-smoke-") as temporary:
        root = Path(temporary)
        venv_dir = root / "venv"
        workspace = root / "workspace"
        home = root / "home"
        workspace.mkdir()
        home.mkdir(mode=0o700)
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)

        python = _venv_python(venv_dir)
        tasksignal = _venv_command(venv_dir, "tasksignal")
        env = os.environ.copy()
        for name in (
            "AUTHOR_HASH_SALT",
            "AUTO_CREATE_TABLES",
            "DATABASE_URL",
            "DEMO_RESET_TOKEN",
            "OPERATOR_SCAN_TOKEN",
            "PYTHONHOME",
            "PYTHONPATH",
            "TASKSIGNAL_API_BASE",
            "TASKSIGNAL_API_URL",
            "TASKSIGNAL_CONFIG_FILE",
            "TASKSIGNAL_DATA_DIR",
            "TASKSIGNAL_OPERATOR_TOKEN",
        ):
            env.pop(name, None)
        env["HOME"] = str(home)
        env["XDG_CONFIG_HOME"] = str(home / ".config")
        env["XDG_DATA_HOME"] = str(home / ".local" / "share")
        env["LLM_PROVIDER"] = "none"

        _run(
            [python, "-m", "pip", "install", "--disable-pip-version-check", str(wheel)],
            cwd=workspace,
            env=env,
        )
        _run([python, "-m", "pip", "check"], cwd=workspace, env=env)
        _run([tasksignal, "--version"], cwd=workspace, env=env)
        _run([tasksignal, "--help"], cwd=workspace, env=env)
        _assert_packaged_inventory(python, cwd=workspace, env=env)
        _assert_mcp_state(python, expected=False, cwd=workspace, env=env)

        init_payload, init_output = _json_cli(
            tasksignal, ["init"], cwd=workspace, env=env
        )
        init_data = init_payload.get("data")
        if not isinstance(init_data, dict):
            raise RuntimeError("tasksignal init returned invalid data")
        config_file = Path(str(init_data["config_file"]))
        if not config_file.is_file():
            raise RuntimeError("tasksignal init did not create its config file")
        if not config_file.resolve().is_relative_to(home.resolve()):
            raise RuntimeError("tasksignal init escaped the isolated test home")
        if os.name == "posix" and stat.S_IMODE(config_file.stat().st_mode) != 0o600:
            raise RuntimeError("tasksignal init config permissions are not 0600")

        _, migrate_output = _json_cli(tasksignal, ["migrate"], cwd=workspace, env=env)
        _, doctor_output = _json_cli(tasksignal, ["doctor"], cwd=workspace, env=env)
        secret_values = []
        for line in config_file.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            _, raw_value = line.split("=", 1)
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError:
                value = raw_value
            if isinstance(value, str) and value:
                secret_values.append(value)
        public_output = init_output + migrate_output + doctor_output
        if any(secret in public_output for secret in secret_values):
            raise RuntimeError("a generated runtime secret appeared in CLI output")

        _run(
            [
                python,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                f"{wheel}[mcp]",
            ],
            cwd=workspace,
            env=env,
        )
        _run([python, "-m", "pip", "check"], cwd=workspace, env=env)
        _assert_mcp_state(python, expected=True, cwd=workspace, env=env)
        _run([tasksignal, "mcp", "--help"], cwd=workspace, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test base and MCP installs of one built TaskSignal wheel."
    )
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args()
    try:
        smoke_wheel(args.wheel)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Built-wheel smoke failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Built-wheel smoke passed on Python {sys.version.split()[0]}: {args.wheel.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
