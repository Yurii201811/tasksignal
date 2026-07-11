"""Installable TaskSignal command-line interface."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import asdict
from typing import Any, Never

from app.core.version import TASKSIGNAL_VERSION


class CLIError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TaskSignalArgumentParser(argparse.ArgumentParser):
    """Route parser failures through the CLI's stable, redacted error envelope."""

    def error(self, _message: str) -> Never:
        raise CLIError(
            "invalid_arguments",
            "Invalid command arguments; use --help to inspect the supported syntax.",
        )


def _csv(value: str | None) -> list[str]:
    return [entry.strip() for entry in (value or "").split(",") if entry.strip()]


def _json_envelope(
    *,
    ok: bool,
    data: object = None,
    code: str | None = None,
    message: str | None = None,
) -> dict[str, object]:
    return {
        "ok": ok,
        "data": data,
        "error": None if ok else {"code": code or "command_failed", "message": message},
        "meta": {"tasksignal_version": TASKSIGNAL_VERSION},
    }


def _emit(envelope: dict[str, Any], *, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    elif envelope.get("ok"):
        data = envelope.get("data")
        if isinstance(data, str):
            print(data)
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        raw_error = envelope.get("error")
        error: dict[str, Any] = raw_error if isinstance(raw_error, dict) else {}
        code = error.get("code", "command_failed")
        message = error.get("message") or "The TaskSignal command failed."
        print(f"TaskSignal error [{code}]: {message}", file=sys.stderr)
    return 0 if envelope.get("ok") else 1


def _add_project_commands(parent: argparse._SubParsersAction) -> None:
    projects = parent.add_parser("projects", help="Create, inspect, update, and run projects.")
    commands = projects.add_subparsers(dest="projects_command", required=True)
    commands.add_parser("list", help="List research projects.")
    get = commands.add_parser("get", help="Read one research project.")
    get.add_argument("project_id")
    create = commands.add_parser("create", help="Create a research project.")
    create.add_argument("--name", required=True)
    create.add_argument("--description")
    create.add_argument("--source-type", default="hackernews")
    create.add_argument("--source-id")
    create.add_argument("--query", default="")
    create.add_argument("--limit", type=int, default=30)
    create.add_argument("--cadence", default="manual")
    create.add_argument("--interval-hours", type=int)
    create.add_argument("--labels", help="Comma-separated project labels.")
    create.add_argument("--disabled", action="store_true")
    update = commands.add_parser("update", help="Update a project with optimistic locking.")
    update.add_argument("project_id")
    update.add_argument("--expected-version", required=True, type=int)
    for option in ("name", "description", "source-type", "source-id", "query", "cadence"):
        update.add_argument(f"--{option}", default=argparse.SUPPRESS)
    update.add_argument("--limit", type=int, default=argparse.SUPPRESS)
    update.add_argument("--interval-hours", type=int, default=argparse.SUPPRESS)
    update.add_argument("--labels", default=argparse.SUPPRESS)
    enabled = update.add_mutually_exclusive_group()
    enabled.add_argument("--enable", action="store_true", default=argparse.SUPPRESS)
    enabled.add_argument("--disable", action="store_true", default=argparse.SUPPRESS)
    run = commands.add_parser("run", help="Run one enabled research project.")
    run.add_argument("project_id")


def _add_run_commands(parent: argparse._SubParsersAction) -> None:
    runs = parent.add_parser("runs", help="Inspect immutable project runs and deltas.")
    commands = runs.add_subparsers(dest="runs_command", required=True)
    listing = commands.add_parser("list", help="List runs for a project.")
    listing.add_argument("project_id")
    delta = commands.add_parser("delta", help="Compare a run with its predecessor.")
    delta.add_argument("project_id")
    delta.add_argument("run_id")


def _add_opportunity_commands(parent: argparse._SubParsersAction) -> None:
    opportunities = parent.add_parser(
        "opportunities", help="Search and review persistent opportunity threads."
    )
    commands = opportunities.add_subparsers(dest="opportunities_command", required=True)
    listing = commands.add_parser("list", help="List opportunity threads.")
    listing.add_argument("--project-id")
    listing.add_argument("--review-state")
    get = commands.add_parser("get", help="Read one opportunity thread.")
    get.add_argument("thread_id")
    search = commands.add_parser("search", help="Search evidence and related threads.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--project-id")
    search.add_argument("--source")
    search.add_argument("--signal-type")
    search.add_argument("--review-state")
    decision = commands.add_parser("decision", help="Set a guarded thread decision.")
    decision.add_argument("thread_id")
    decision.add_argument("--review-state", required=True)
    decision.add_argument("--expected-version", type=int, required=True)
    decision.add_argument("--review-note")
    detach = commands.add_parser("detach", help="Detach one snapshot into a new thread.")
    detach.add_argument("thread_id")
    detach.add_argument("snapshot_id")
    detach.add_argument("--expected-version", type=int, required=True)


def _add_evidence_commands(parent: argparse._SubParsersAction) -> None:
    evidence = parent.add_parser("evidence", help="Append versioned evidence labels.")
    commands = evidence.add_subparsers(dest="evidence_command", required=True)
    label = commands.add_parser("label", help="Append a human evidence label.")
    label.add_argument("item_id")
    label.add_argument("--label", required=True)
    label.add_argument("--expected-version", type=int, required=True)
    label.add_argument("--note")


def _add_packet_commands(parent: argparse._SubParsersAction) -> None:
    packets = parent.add_parser("packets", help="Create, verify, and download build packets.")
    commands = packets.add_subparsers(dest="packets_command", required=True)
    listing = commands.add_parser("list", help="List packets for an opportunity thread.")
    listing.add_argument("thread_id")
    listing.add_argument("--limit", type=int, default=20)
    listing.add_argument("--offset", type=int, default=0)
    get = commands.add_parser("get", help="Read one immutable build packet.")
    get.add_argument("packet_id")
    create = commands.add_parser("create", help="Create an immutable build packet.")
    create.add_argument("thread_id")
    create.add_argument("--expected-version", type=int, required=True)
    create.add_argument("--use-configured-ai", action="store_true")
    verify = commands.add_parser("verify", help="Verify packet hashes and inventory.")
    verify.add_argument("packet_id")
    download = commands.add_parser("download", help="Download a verified packet ZIP.")
    download.add_argument("packet_id")
    download.add_argument("--output", required=True)


def _add_session_commands(parent: argparse._SubParsersAction) -> None:
    sessions = parent.add_parser("sessions", help="Approve and audit local agent sessions.")
    commands = sessions.add_subparsers(dest="sessions_command", required=True)
    commands.add_parser("list", help="List local agent sessions.")
    get = commands.add_parser("get", help="Read one agent session.")
    get.add_argument("session_id")
    approve = commands.add_parser("approve", help="Approve one pending process session.")
    approve.add_argument("session_id")
    approve.add_argument("--expected-version", type=int, required=True)
    approve.add_argument("--use-configured-ai", action="store_true")
    revoke = commands.add_parser("revoke", help="Revoke one process session.")
    revoke.add_argument("session_id")
    revoke.add_argument("--expected-version", type=int, required=True)
    actions = commands.add_parser("actions", help="Read redacted append-only action audit.")
    actions.add_argument("session_id")
    actions.add_argument("--limit", type=int, default=100)
    actions.add_argument("--offset", type=int, default=0)


def build_parser() -> argparse.ArgumentParser:
    parser = TaskSignalArgumentParser(
        prog="tasksignal",
        description="Local evidence-to-build workbench.",
    )
    parser.add_argument("--version", action="version", version=f"TaskSignal {TASKSIGNAL_VERSION}")
    parser.add_argument("--json", action="store_true", help="Emit one JSON envelope to stdout.")
    parser.add_argument("--api-url", help="Override TASKSIGNAL_API_URL for this command.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="Create local data and a permission-0600 config file.")
    migrate = commands.add_parser(
        "migrate", help="Back up SQLite and migrate to the packaged schema."
    )
    migrate.add_argument(
        "--fingerprint",
        action="store_true",
        help="Inspect a nonempty unversioned schema without changing it.",
    )
    migrate.add_argument("--stamp-revision", help="Explicit revision for a reviewed schema.")
    migrate.add_argument("--expected-fingerprint")
    migrate.add_argument(
        "--acknowledge-schema-matches-revision",
        action="store_true",
        help="Confirm manual inspection before an explicit stamp.",
    )
    serve = commands.add_parser("serve", help="Run the schema-checked local API server.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("doctor", help="Check local config, schema, API, and MCP readiness.")
    commands.add_parser("mcp", help="Run the guarded MCP server over stdio.")
    _add_project_commands(commands)
    _add_run_commands(commands)
    _add_opportunity_commands(commands)
    _add_evidence_commands(commands)
    _add_packet_commands(commands)
    _add_session_commands(commands)
    return parser


def _activate_runtime_config(config: Any) -> None:
    if hasattr(config, "as_environment"):
        values = config.as_environment()
    else:
        values = {
            "DATABASE_URL": config.database_url,
            "AUTHOR_HASH_SALT": config.author_hash_salt,
            "DEMO_RESET_TOKEN": config.demo_reset_token,
            "OPERATOR_SCAN_TOKEN": config.operator_scan_token,
        }
    for key, value in values.items():
        if value is not None:
            os.environ.setdefault(key, str(value))
    os.environ["TASKSIGNAL_PACKAGED_MODE"] = "1"
    os.environ["AUTO_CREATE_TABLES"] = "false"
    operator_token = values.get("OPERATOR_SCAN_TOKEN")
    if operator_token:
        os.environ.setdefault("TASKSIGNAL_OPERATOR_TOKEN", str(operator_token))


def _local_command(args: argparse.Namespace) -> dict[str, Any] | None:
    from app import packaged_runtime

    if args.command == "init":
        init_result = packaged_runtime.initialize_runtime()
        return _json_envelope(
            ok=True,
            data={
                "config_created": init_result.config_created,
                "data_dir": str(init_result.paths.data_dir),
                "config_file": str(init_result.paths.config_file),
                "database_file": str(init_result.paths.database_file),
            },
        )

    paths = packaged_runtime.resolve_runtime_paths()
    if args.command == "migrate":
        if args.fingerprint and (
            args.stamp_revision
            or args.expected_fingerprint
            or args.acknowledge_schema_matches_revision
        ):
            raise CLIError(
                "invalid_migration_options",
                "--fingerprint cannot be combined with stamp options.",
            )
        if bool(args.stamp_revision) != bool(args.expected_fingerprint):
            raise CLIError(
                "invalid_migration_options",
                "Explicit stamping requires --stamp-revision and --expected-fingerprint.",
            )
        if args.acknowledge_schema_matches_revision and not args.stamp_revision:
            raise CLIError(
                "invalid_migration_options",
                "The acknowledgement flag is valid only with an explicit stamp.",
            )

    if args.command == "doctor":
        initialized = paths.config_file.is_file()
        config_error: dict[str, str] | None = None
        schema: dict[str, Any] | None = None
        if initialized:
            try:
                config = packaged_runtime.load_runtime_config(paths=paths)
                _activate_runtime_config(config)
                schema = asdict(packaged_runtime.inspect_schema(config.database_url))
            except packaged_runtime.PackagedRuntimeError as exc:
                config_error = exc.as_dict()

        from app.cli_http import TaskSignalHttpClient

        try:
            with TaskSignalHttpClient(base_url=args.api_url) as client:
                health = client.health()
        except (OSError, RuntimeError, ValueError):
            health = {
                "ok": False,
                "data": None,
                "error": {
                    "code": "health_check_failed",
                    "message": "TaskSignal API health could not be checked.",
                },
                "meta": {},
            }
        mcp_installed = importlib.util.find_spec("mcp") is not None
        ready = bool(
            initialized
            and config_error is None
            and schema is not None
            and schema["state"] == "current"
        )
        data = {
            "ready": ready,
            "initialized": initialized,
            "config_file": str(paths.config_file),
            "data_dir": str(paths.data_dir),
            "config_error": config_error,
            "schema": schema,
            "api": health,
            "api_running": bool(health.get("ok")),
            "mcp_extra_installed": mcp_installed,
        }
        return _json_envelope(
            ok=ready,
            data=data,
            code=None if ready else "local_setup_incomplete",
            message=None if ready else "Run `tasksignal init` and `tasksignal migrate`.",
        )

    config = packaged_runtime.load_runtime_config(paths=paths)
    _activate_runtime_config(config)
    if args.command == "migrate":
        if args.fingerprint:
            return _json_envelope(
                ok=True,
                data=asdict(packaged_runtime.fingerprint_schema(config.database_url)),
            )
        migration_result: packaged_runtime.MigrationResult | packaged_runtime.StampResult
        if args.stamp_revision:
            migration_result = packaged_runtime.stamp_inspected_schema(
                config.database_url,
                revision=args.stamp_revision,
                expected_fingerprint=args.expected_fingerprint,
                acknowledge_schema_matches_revision=(args.acknowledge_schema_matches_revision),
            )
        else:
            migration_result = packaged_runtime.migrate_database(config.database_url)
        data = asdict(migration_result)
        if data.get("backup_path") is not None:
            data["backup_path"] = str(data["backup_path"])
        return _json_envelope(ok=True, data=data)
    status = packaged_runtime.inspect_schema(config.database_url)
    if status.state != "current":
        raise CLIError(
            "schema_not_current",
            "The database schema is not current; run `tasksignal migrate` first.",
        )
    if args.command == "serve":
        if args.host not in {"localhost", "127.0.0.1", "::1"}:
            raise CLIError("non_loopback_host", "Packaged serve accepts only loopback hosts.")
        if not 1 <= args.port <= 65535:
            raise CLIError("invalid_port", "Port must be between 1 and 65535.")
        import uvicorn

        uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info")
        return None
    if args.command == "mcp":
        if importlib.util.find_spec("mcp") is None:
            raise CLIError(
                "mcp_extra_missing",
                'Install MCP support with `uv tool install "tasksignal[mcp]"`.',
            )
        from app.mcp_server.server import run_mcp_server

        run_mcp_server(approval_callback=_interactive_tty_approval)
        return None
    raise CLIError("unknown_command", "Unknown local command.")


def _interactive_tty_approval(runtime: Any) -> None:
    if not sys.stdin.isatty():
        return
    print(
        "Approve non-destructive TaskSignal MCP writes for this process? [y/N] ",
        end="",
        file=sys.stderr,
    )
    if sys.stdin.readline().strip().casefold() not in {"y", "yes"}:
        return
    print("Also allow configured AI generation (may incur cost)? [y/N] ", end="", file=sys.stderr)
    use_ai = sys.stdin.readline().strip().casefold() in {"y", "yes"}
    runtime.approve_interactive(use_configured_ai=use_ai)


def _http_command(args: argparse.Namespace) -> dict[str, Any]:
    from app.cli_http import TaskSignalHttpClient

    try:
        from app import packaged_runtime

        paths = packaged_runtime.resolve_runtime_paths()
        if paths.config_file.is_file():
            _activate_runtime_config(packaged_runtime.load_runtime_config(paths=paths))
    except (OSError, RuntimeError, ValueError):
        pass

    with TaskSignalHttpClient(base_url=args.api_url) as client:
        if args.command == "projects":
            if args.projects_command == "list":
                return client.projects_list()
            if args.projects_command == "get":
                return client.projects_get(args.project_id)
            if args.projects_command == "create":
                return client.projects_create(
                    name=args.name,
                    description=args.description,
                    source_type=args.source_type,
                    source_id=args.source_id,
                    query=args.query,
                    limit=args.limit,
                    cadence=args.cadence,
                    schedule_interval_hours=args.interval_hours,
                    labels=_csv(args.labels),
                    enabled=not args.disabled,
                )
            if args.projects_command == "update":
                updates = {
                    field: getattr(args, field)
                    for field in (
                        "name",
                        "description",
                        "source_type",
                        "source_id",
                        "query",
                        "limit",
                        "cadence",
                    )
                    if hasattr(args, field)
                }
                if hasattr(args, "interval_hours"):
                    updates["schedule_interval_hours"] = args.interval_hours
                if hasattr(args, "labels"):
                    updates["labels"] = _csv(args.labels)
                if hasattr(args, "enable"):
                    updates["enabled"] = True
                if hasattr(args, "disable"):
                    updates["enabled"] = False
                return client.projects_update(
                    args.project_id,
                    expected_version=args.expected_version,
                    **updates,
                )
            return client.projects_run(args.project_id)
        if args.command == "runs":
            if args.runs_command == "list":
                return client.runs_list(args.project_id)
            return client.runs_delta(args.project_id, args.run_id)
        if args.command == "opportunities":
            if args.opportunities_command == "list":
                return client.opportunities_list(
                    project_id=args.project_id,
                    review_state=args.review_state,
                )
            if args.opportunities_command == "get":
                return client.opportunities_get(args.thread_id)
            if args.opportunities_command == "search":
                return client.opportunities_search(
                    query=args.query,
                    limit=args.limit,
                    project_id=args.project_id,
                    source=args.source,
                    signal_type=args.signal_type,
                    review_state=args.review_state,
                )
            if args.opportunities_command == "decision":
                return client.opportunities_decision(
                    args.thread_id,
                    review_state=args.review_state,
                    expected_version=args.expected_version,
                    review_note=args.review_note,
                )
            return client.opportunities_detach(
                args.thread_id,
                args.snapshot_id,
                expected_version=args.expected_version,
            )
        if args.command == "evidence":
            return client.evidence_label(
                args.item_id,
                label=args.label,
                user_note=args.note,
                expected_version=args.expected_version,
            )
        if args.command == "packets":
            if args.packets_command == "list":
                return client.packets_list(args.thread_id, limit=args.limit, offset=args.offset)
            if args.packets_command == "get":
                return client.packets_get(args.packet_id)
            if args.packets_command == "create":
                return client.packets_create(
                    args.thread_id,
                    expected_version=args.expected_version,
                    use_configured_ai=args.use_configured_ai,
                )
            if args.packets_command == "verify":
                return client.packets_verify(args.packet_id)
            return client.packets_download(args.packet_id, output_path=args.output)
        if args.sessions_command == "list":
            return client.sessions_list()
        if args.sessions_command == "get":
            return client.sessions_get(args.session_id)
        if args.sessions_command == "approve":
            return client.sessions_approve(
                args.session_id,
                expected_version=args.expected_version,
                use_configured_ai=args.use_configured_ai,
            )
        if args.sessions_command == "revoke":
            return client.sessions_revoke(
                args.session_id,
                expected_version=args.expected_version,
            )
        return client.sessions_actions(args.session_id, limit=args.limit, offset=args.offset)


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in raw_argv
    normalized_argv = [argument for argument in raw_argv if argument != "--json"]
    parser = build_parser()
    try:
        args = parser.parse_args(normalized_argv)
        if args.command in {"init", "migrate", "serve", "doctor", "mcp"}:
            envelope = _local_command(args)
        else:
            envelope = _http_command(args)
        return 0 if envelope is None else _emit(envelope, json_mode=json_mode)
    except CLIError as exc:
        return _emit(
            _json_envelope(ok=False, code=exc.code, message=exc.message),
            json_mode=json_mode,
        )
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        code = getattr(exc, "code", "internal_error")
        message = str(exc) if code != "internal_error" else "The TaskSignal command failed."
        return _emit(
            _json_envelope(ok=False, code=code, message=message),
            json_mode=json_mode,
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
