import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("tasksignal_doctor", ROOT / "scripts/doctor.py")
assert SPEC and SPEC.loader
doctor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = doctor
SPEC.loader.exec_module(doctor)


def test_doctor_uses_api_project_virtualenv() -> None:
    assert doctor.VENV_BIN == ROOT / "apps" / "api" / ".venv" / "bin"


def test_missing_tool_guidance_names_api_project_virtualenv(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda _path: False)
    monkeypatch.setattr(doctor.shutil, "which", lambda _command: None)

    check = doctor.check_python_tool("pytest", "pytest")

    assert check.status == "fail"
    assert "apps/api/.venv/bin/pytest" in check.detail


def test_missing_frontend_dependencies_point_to_setup(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda _path: False)

    check = doctor.check_frontend_dependencies()

    assert check.status == "fail"
    assert "make setup" in check.detail


def test_missing_root_env_is_ready_for_fixture_workflow(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda _path: False)

    check = doctor.check_env_file()

    assert check.status == "ok"
    assert "not required" in check.detail


def test_present_root_env_points_to_process_specific_files(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda _path: True)

    check = doctor.check_env_file()

    assert check.status == "warn"
    assert "apps/api/.env" in check.detail
    assert "apps/web/.env.local" in check.detail
