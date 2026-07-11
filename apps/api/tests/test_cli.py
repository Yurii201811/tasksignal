from __future__ import annotations

import json

import app.cli as cli


def test_help_exposes_local_and_noun_first_command_families() -> None:
    help_text = cli.build_parser().format_help()

    for command in (
        "init",
        "migrate",
        "serve",
        "doctor",
        "mcp",
        "projects",
        "runs",
        "opportunities",
        "evidence",
        "packets",
        "sessions",
    ):
        assert command in help_text


def test_json_flag_works_after_nested_command_and_stdout_is_one_envelope(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli,
        "_http_command",
        lambda _args: {
            "ok": True,
            "data": [{"id": "project-1"}],
            "error": None,
            "meta": {"status": 200},
        },
    )

    exit_code = cli.main(["projects", "list", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "ok": True,
        "data": [{"id": "project-1"}],
        "error": None,
        "meta": {"status": 200},
    }
    assert captured.out.count("\n") == 1


def test_unexpected_failures_are_generic_and_do_not_echo_secret_values(
    monkeypatch,
    capsys,
) -> None:
    def fail(_args):
        raise ValueError("token=CLI-SECRET-MUST-NOT-LEAK")

    monkeypatch.setattr(cli, "_http_command", fail)

    exit_code = cli.main(["--json", "projects", "list"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["error"]["code"] == "internal_error"
    assert "CLI-SECRET-MUST-NOT-LEAK" not in captured.out
    assert captured.err == ""


def test_json_parser_failures_use_one_stable_redacted_envelope(capsys) -> None:
    exit_code = cli.main(["--json", "projects", "list", "--unknown", "CLI-SECRET-MUST-NOT-LEAK"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    assert payload["ok"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == "invalid_arguments"
    assert "CLI-SECRET-MUST-NOT-LEAK" not in captured.out


def test_json_unknown_command_is_not_an_argparse_stderr_exit(capsys) -> None:
    exit_code = cli.main(["definitely-not-a-command", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert captured.err == ""
    assert payload["error"]["code"] == "invalid_arguments"


def test_update_parser_preserves_only_explicit_fields() -> None:
    args = cli.build_parser().parse_args(
        [
            "projects",
            "update",
            "project-1",
            "--expected-version",
            "4",
            "--name",
            "Updated",
            "--disable",
        ]
    )

    assert args.expected_version == 4
    assert args.name == "Updated"
    assert args.disable is True
    assert not hasattr(args, "description")
    assert not hasattr(args, "enable")


def test_doctor_before_init_returns_actionable_redacted_diagnostics(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    class HealthyClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc_info) -> None:
            pass

        def health(self):
            return {
                "ok": True,
                "data": {"status": "ok"},
                "error": None,
                "meta": {"status": 200},
            }

    monkeypatch.setenv("TASKSIGNAL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TASKSIGNAL_CONFIG_FILE", str(tmp_path / "config.env"))
    monkeypatch.setattr("app.cli_http.TaskSignalHttpClient", HealthyClient)

    exit_code = cli.main(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error"]["code"] == "local_setup_incomplete"
    assert payload["data"]["ready"] is False
    assert payload["data"]["initialized"] is False
    assert payload["data"]["schema"] is None
    assert payload["data"]["api"]["ok"] is True
    assert "AUTHOR_HASH_SALT" not in json.dumps(payload)


def test_migrate_rejects_ambiguous_recovery_options_before_loading_config(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    monkeypatch.setenv("TASKSIGNAL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TASKSIGNAL_CONFIG_FILE", str(tmp_path / "missing.env"))

    exit_code = cli.main(
        [
            "migrate",
            "--fingerprint",
            "--acknowledge-schema-matches-revision",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["error"]["code"] == "invalid_migration_options"
    assert "not_initialized" not in json.dumps(payload)


def test_doctor_reports_ready_schema_when_local_api_is_not_running(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    class OfflineClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc_info) -> None:
            pass

        def health(self):
            return {
                "ok": False,
                "data": None,
                "error": {"code": "connection_failed", "message": "API is not running."},
                "meta": {},
            }

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("TASKSIGNAL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TASKSIGNAL_CONFIG_FILE", str(tmp_path / "config.env"))
    monkeypatch.setattr("app.cli_http.TaskSignalHttpClient", OfflineClient)

    assert cli.main(["--json", "init"]) == 0
    assert cli.main(["--json", "migrate"]) == 0
    capsys.readouterr()

    exit_code = cli.main(["--json", "doctor"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["data"]["ready"] is True
    assert payload["data"]["schema"]["state"] == "current"
    assert payload["data"]["api_running"] is False
