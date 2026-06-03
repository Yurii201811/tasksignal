#!/usr/bin/env python3
"""Small local CLI for TaskSignal's research-to-build workflow."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_API_BASE = "http://127.0.0.1:8000"


def request_json(
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    operator_token: str | None = None,
) -> dict | list:
    base = os.environ.get("TASKSIGNAL_API_BASE", DEFAULT_API_BASE).rstrip("/")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if operator_token:
        headers["X-Operator-Scan-Token"] = operator_token
    request = Request(f"{base}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise SystemExit(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"Could not reach TaskSignal API at {base}: {exc.reason}") from exc


def print_json(value: dict | list) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def command_readiness(_args: argparse.Namespace) -> None:
    print_json(request_json("/api/readiness"))


def command_integrations(_args: argparse.Namespace) -> None:
    integrations = request_json("/api/integrations")
    if not isinstance(integrations, list):
        print_json(integrations)
        return
    for integration in integrations:
        print(
            f"{integration['id']}: {integration['status']} "
            f"({integration['credential_state']})"
        )


def command_projects(_args: argparse.Namespace) -> None:
    projects = request_json("/api/research-projects")
    if not isinstance(projects, list):
        print_json(projects)
        return
    for project in projects:
        status = project.get("last_scan_status") or "not run"
        next_run = project.get("next_run_at") or "manual"
        print(f"{project['id']}  {project['name']}  {status}  next={next_run}")


def command_create_project(args: argparse.Namespace) -> None:
    labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    payload = {
        "name": args.name,
        "description": args.description,
        "source_type": args.source,
        "query": args.query,
        "limit": args.limit,
        "cadence": args.cadence,
        "schedule_interval_hours": args.interval_hours,
        "labels": labels,
        "enabled": True,
    }
    print_json(request_json("/api/research-projects", method="POST", payload=payload))


def command_run_project(args: argparse.Namespace) -> None:
    token = args.operator_token or os.environ.get("TASKSIGNAL_OPERATOR_TOKEN")
    print_json(
        request_json(
            f"/api/research-projects/{args.project_id}/run",
            method="POST",
            operator_token=token,
        )
    )


def command_run_due(args: argparse.Namespace) -> None:
    token = args.operator_token or os.environ.get("TASKSIGNAL_OPERATOR_TOKEN")
    print_json(
        request_json(
            "/api/research-projects/run-due",
            method="POST",
            operator_token=token,
        )
    )


def command_opportunities(args: argparse.Namespace) -> None:
    opportunities = request_json("/api/opportunities")
    if not isinstance(opportunities, list):
        print_json(opportunities)
        return
    for opportunity in opportunities[: args.limit]:
        score = round(float(opportunity["opportunity_score"]) * 100)
        print(f"{opportunity['id']}  {score:>3}  {opportunity['title']}")


def command_task_pack(args: argparse.Namespace) -> None:
    pack = request_json(f"/api/opportunities/{args.opportunity_id}/task-pack.json")
    if not isinstance(pack, dict):
        print_json(pack)
        return
    markdown = pack["markdown"]
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
        print(args.output)
    else:
        print(markdown)


def command_enhance(args: argparse.Namespace) -> None:
    payload = request_json(
        f"/api/opportunities/{args.opportunity_id}/enhance?apply={str(args.apply).lower()}",
        method="POST",
    )
    if args.json:
        print_json(payload)
        return
    if not isinstance(payload, dict):
        print_json(payload)
        return
    print(f"{payload['provider']}:{payload['model']} applied={payload['applied']}")
    print(payload["enhanced_prompt"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TaskSignal local CLI")
    subcommands = parser.add_subparsers(required=True)

    readiness = subcommands.add_parser("readiness")
    readiness.set_defaults(func=command_readiness)

    integrations = subcommands.add_parser("integrations")
    integrations.set_defaults(func=command_integrations)

    projects = subcommands.add_parser("projects")
    projects.set_defaults(func=command_projects)

    create_project = subcommands.add_parser("create-project")
    create_project.add_argument("--name", required=True)
    create_project.add_argument("--description", default=None)
    create_project.add_argument("--source", default="hackernews")
    create_project.add_argument("--query", default="")
    create_project.add_argument("--limit", type=int, default=30)
    create_project.add_argument("--cadence", default="manual")
    create_project.add_argument("--interval-hours", type=int, default=None)
    create_project.add_argument("--labels", default="")
    create_project.set_defaults(func=command_create_project)

    run_project = subcommands.add_parser("run-project")
    run_project.add_argument("project_id")
    run_project.add_argument("--operator-token", default=None)
    run_project.set_defaults(func=command_run_project)

    run_due = subcommands.add_parser("run-due")
    run_due.add_argument("--operator-token", default=None)
    run_due.set_defaults(func=command_run_due)

    opportunities = subcommands.add_parser("opportunities")
    opportunities.add_argument("--limit", type=int, default=10)
    opportunities.set_defaults(func=command_opportunities)

    task_pack = subcommands.add_parser("task-pack")
    task_pack.add_argument("opportunity_id")
    task_pack.add_argument("--output", default=None)
    task_pack.set_defaults(func=command_task_pack)

    enhance = subcommands.add_parser("enhance")
    enhance.add_argument("opportunity_id")
    enhance.add_argument("--apply", action="store_true")
    enhance.add_argument("--json", action="store_true")
    enhance.set_defaults(func=command_enhance)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
