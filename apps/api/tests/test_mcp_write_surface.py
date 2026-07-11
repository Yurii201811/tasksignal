from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

import app.services.mcp_surface.writes as mcp_writes
from app.db.session import SessionLocal
from app.models.all_models import (
    AgentAction,
    AgentSession,
    BuildPacket,
    Label,
    NormalizedItem,
    OpportunityDecisionEvent,
    ResearchProject,
    ResearchProjectRun,
    ScanJob,
)
from app.services.agent_actions.service import _authorize_and_reserve_agent_action
from app.services.agent_sessions import (
    STANDARD_WRITE_CAPABILITIES,
    hash_session_secret,
    revoke_session,
)
from app.services.build_packets.enhancement import ENHANCEABLE_FILENAMES
from app.services.ingestion.connectors import BaseConnector
from app.services.ingestion.types import RawFetchedItem, utc_now
from app.services.mcp_surface.writes import MCP_WRITE_OPERATIONS, execute_mcp_write
from app.workers import scan_pipeline

RAW_SECRET = "mcp-write-surface-secret-with-at-least-thirty-two-bytes"


def _approved_session(
    *,
    configured_ai: bool = False,
    raw_secret: str = RAW_SECRET,
) -> AgentSession:
    now = datetime.now(UTC)
    capabilities = set(STANDARD_WRITE_CAPABILITIES)
    if configured_ai:
        capabilities.add("use_configured_ai")
    return AgentSession(
        process_instance_id=uuid4(),
        client_name="MCP write surface test",
        client_version="1.0",
        transport="stdio",
        secret_hash=hash_session_secret(raw_secret),
        status="approved",
        requested_capabilities_json=sorted(capabilities),
        approved_capabilities_json=sorted(capabilities),
        approval_source="ui",
        approved_at=now,
        last_heartbeat_at=now,
        expires_at=now + timedelta(minutes=5),
        version=2,
        created_at=now,
        updated_at=now,
    )


def _persist_session(
    *,
    configured_ai: bool = False,
    raw_secret: str = RAW_SECRET,
):
    with SessionLocal() as db:
        session = _approved_session(
            configured_ai=configured_ai,
            raw_secret=raw_secret,
        )
        db.add(session)
        db.commit()
        return session.id


def _persist_pending_session():
    with SessionLocal() as db:
        session = _approved_session()
        session.status = "pending"
        session.approved_capabilities_json = []
        session.approval_source = None
        session.approved_at = None
        session.version = 1
        db.add(session)
        db.commit()
        return session.id


def _call(
    session_id,
    operation: str,
    *,
    key: str,
    expected_version: int,
    arguments: dict,
    raw_secret: str = RAW_SECRET,
):
    return execute_mcp_write(
        SessionLocal,
        session_id=session_id,
        raw_session_secret=raw_secret,
        operation=operation,
        idempotency_key=key,
        expected_version=expected_version,
        arguments=arguments,
    )


def _reserve_run_without_mutation(session_id, *, key: str, project_id: str):
    request = {"project_id": project_id, "expected_version": 1}
    correlation_id = mcp_writes._run_scan_id(key, request)
    with SessionLocal() as db:
        claim = _authorize_and_reserve_agent_action(
            db,
            session_id=session_id,
            raw_session_secret=RAW_SECRET,
            tool_name="run_project",
            idempotency_key=key,
            request=request,
            correlation_id=correlation_id,
        )
        db.commit()
    assert claim.outcome == "reserved"
    return claim, request


def test_surface_exposes_exact_six_operations_and_create_replays_safely(client) -> None:
    del client
    assert MCP_WRITE_OPERATIONS == frozenset(
        {
            "create_project",
            "update_project",
            "run_project",
            "set_opportunity_decision",
            "append_evidence_label",
            "create_build_packet",
        }
    )
    session_id = _persist_session()
    arguments = {
        "name": "Private project name",
        "description": "private description",
        "source_type": "fixture",
        "query": "private research query",
        "limit": 10,
        "cadence": "manual",
        "labels": ["private-label"],
        "enabled": True,
    }

    created = _call(
        session_id,
        "create_project",
        key="create-project-write-surface-0001",
        expected_version=1,
        arguments=arguments,
    )
    replay = _call(
        session_id,
        "create_project",
        key="create-project-write-surface-0001",
        expected_version=1,
        arguments=arguments,
    )
    collision = _call(
        session_id,
        "create_project",
        key="create-project-write-surface-0001",
        expected_version=1,
        arguments={**arguments, "name": "Different private name"},
    )

    assert created["ok"] is True
    assert created["outcome"] == "succeeded"
    assert created["result"]["version"] == 1
    assert replay["ok"] is True
    assert replay["outcome"] == "replay"
    assert replay["result"] == created["result"]
    assert collision["ok"] is False
    assert collision["outcome"] == "conflict"
    assert collision["error"] == {"code": "idempotency_conflict"}

    serialized = json.dumps([created, replay, collision], sort_keys=True)
    assert "Private project name" not in serialized
    assert "private research query" not in serialized
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ResearchProject)) == 1
        events = list(db.scalars(select(AgentAction).order_by(AgentAction.created_at)))
    assert [event.event_status for event in events] == [
        "reserved",
        "succeeded",
        "replayed",
        "conflict",
    ]
    assert "private" not in json.dumps(
        [event.request_summary_json for event in events], sort_keys=True
    ).lower()


def test_project_update_returns_version_conflict_and_durable_failed_audit(client) -> None:
    del client
    session_id = _persist_session()
    created = _call(
        session_id,
        "create_project",
        key="create-before-update-surface-0001",
        expected_version=1,
        arguments={
            "name": "Versioned project",
            "source_type": "fixture",
            "query": "workflow",
        },
    )
    project_id = created["result"]["project_id"]

    updated = _call(
        session_id,
        "update_project",
        key="update-project-write-surface-0001",
        expected_version=1,
        arguments={"project_id": project_id, "name": "Updated project"},
    )
    stale = _call(
        session_id,
        "update_project",
        key="update-project-write-surface-0002",
        expected_version=1,
        arguments={"project_id": project_id, "name": "Must not win"},
    )

    assert updated["ok"] is True
    assert updated["result"]["version"] == 2
    assert stale["ok"] is False
    assert stale["outcome"] == "error"
    assert stale["error"] == {
        "code": "version_conflict",
        "expected_version": 1,
        "current_version": 2,
    }
    with SessionLocal() as db:
        project = db.get(ResearchProject, UUID(project_id))
        failed = db.scalar(
            select(AgentAction)
            .where(
                AgentAction.tool_name == "update_project",
                AgentAction.event_status == "failed",
            )
            .order_by(AgentAction.created_at.desc())
        )
    assert project is not None
    assert project.name == "Updated project"
    assert failed is not None
    assert failed.error_code == "version_conflict"
    assert failed.result_summary_json == {
        "current_version": 2,
        "expected_version": 1,
    }

    replay = _call(
        session_id,
        "update_project",
        key="update-project-write-surface-0002",
        expected_version=1,
        arguments={"project_id": project_id, "name": "Must not win"},
    )
    assert replay["outcome"] == "replay"
    assert replay["result"] is None
    assert replay["error"] == stale["error"]


def test_noop_project_update_redacts_preexisting_metadata_from_result(client) -> None:
    del client
    session_id = _persist_session()
    created = _call(
        session_id,
        "create_project",
        key="create-before-redacted-noop-0001",
        expected_version=1,
        arguments={"name": "Redacted no-op", "source_type": "fixture"},
    )
    project_id = UUID(created["result"]["project_id"])
    with SessionLocal() as db:
        project = db.get(ResearchProject, project_id)
        assert project is not None
        project.cadence = "token=PREEXISTING-PROJECT-SECRET"
        db.commit()

    unchanged = _call(
        session_id,
        "update_project",
        key="redacted-noop-project-0001",
        expected_version=1,
        arguments={"project_id": str(project_id)},
    )

    assert unchanged["ok"] is True
    assert unchanged["result"]["status"] == "unchanged"
    assert unchanged["result"]["cadence"] == "[REDACTED]"
    assert "PREEXISTING-PROJECT-SECRET" not in json.dumps(unchanged)


def test_run_project_reserves_one_scan_and_retry_replays(client) -> None:
    del client
    session_id = _persist_session()
    created = _call(
        session_id,
        "create_project",
        key="create-before-run-surface-0001",
        expected_version=1,
        arguments={
            "name": "Fixture scan",
            "source_type": "fixture",
            "query": "workflow",
            "limit": 10,
        },
    )
    project_id = created["result"]["project_id"]
    arguments = {"project_id": project_id}

    ran = _call(
        session_id,
        "run_project",
        key="run-project-write-surface-0001",
        expected_version=1,
        arguments=arguments,
    )
    replay = _call(
        session_id,
        "run_project",
        key="run-project-write-surface-0001",
        expected_version=1,
        arguments=arguments,
    )

    assert ran["ok"] is True
    assert ran["result"]["status"] == "completed"
    assert ran["result"]["version"] == 2
    assert replay["ok"] is True
    assert replay["outcome"] == "replay"
    assert replay["result"] == ran["result"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ScanJob)) == 1
        project = db.get(ResearchProject, UUID(project_id))
        research_run = db.scalar(select(ResearchProjectRun))
    assert project is not None
    assert research_run is not None
    assert ran["result"]["run_id"] == str(research_run.id)
    assert ran["result"]["id"] == str(research_run.scan_id)
    assert project.run_count == 1
    assert project.version == 2


def test_concurrent_identical_run_reports_in_progress_without_second_scan(
    client,
    monkeypatch,
) -> None:
    del client
    entered_fetch = threading.Event()
    release_fetch = threading.Event()

    class SlowFixtureConnector(BaseConnector):
        name = "slowfixture"

        def fetch(self, query: str = "", limit: int = 50):
            del query, limit
            entered_fetch.set()
            assert release_fetch.wait(timeout=10)
            return []

    monkeypatch.setitem(
        scan_pipeline.CONNECTOR_FACTORIES,
        "slowfixture",
        SlowFixtureConnector,
    )
    session_id = _persist_session()
    created = _call(
        session_id,
        "create_project",
        key="create-before-concurrent-run-0001",
        expected_version=1,
        arguments={
            "name": "Slow fixture scan",
            "source_type": "slowfixture",
            "query": "workflow",
        },
    )
    project_id = created["result"]["project_id"]
    call = lambda: _call(  # noqa: E731 - compact callable for the executor
        session_id,
        "run_project",
        key="concurrent-run-write-surface-0001",
        expected_version=1,
        arguments={"project_id": project_id},
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(call)
        assert entered_fetch.wait(timeout=10)
        in_progress = executor.submit(call).result(timeout=10)
        release_fetch.set()
        first = first_future.result(timeout=10)

    assert in_progress["ok"] is False
    assert in_progress["outcome"] == "in_progress"
    assert in_progress["error"] == {"code": "idempotency_in_progress"}
    assert first["ok"] is True
    replay = call()
    assert replay["outcome"] == "replay"
    assert replay["result"] == first["result"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ScanJob)) == 1


def test_revoke_during_fetch_blocks_evidence_persistence_and_terminal_success(
    client,
    monkeypatch,
) -> None:
    del client
    entered_fetch = threading.Event()
    release_fetch = threading.Event()

    class RevokedFetchConnector(BaseConnector):
        name = "revokedfetch"

        def fetch(self, query: str = "", limit: int = 50):
            del query, limit
            entered_fetch.set()
            assert release_fetch.wait(timeout=10)
            return [
                RawFetchedItem(
                    source="revokedfetch",
                    external_id="must-not-persist",
                    raw_json={
                        "title": "Must not persist after revocation",
                        "body": "This evidence must be rejected before normalization.",
                        "url": "https://example.test/revoked",
                        "created_at": "2026-07-11T00:00:00Z",
                    },
                    fetched_at=utc_now(),
                )
            ]

    monkeypatch.setitem(
        scan_pipeline.CONNECTOR_FACTORIES,
        "revokedfetch",
        RevokedFetchConnector,
    )
    session_id = _persist_session()
    created = _call(
        session_id,
        "create_project",
        key="create-before-revoked-fetch-0001",
        expected_version=1,
        arguments={
            "name": "Revoked fetch",
            "source_type": "revokedfetch",
            "query": "workflow",
        },
    )
    project_id = created["result"]["project_id"]

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _call,
            session_id,
            "run_project",
            key="revoked-fetch-write-surface-0001",
            expected_version=1,
            arguments={"project_id": project_id},
        )
        assert entered_fetch.wait(timeout=10)
        with SessionLocal() as db:
            session = db.get(AgentSession, session_id)
            assert session is not None
            revoke_session(session, expected_version=session.version)
            db.commit()
        release_fetch.set()
        denied = future.result(timeout=10)

    assert denied["ok"] is False
    assert denied["error"] == {"code": "session_state_error"}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(NormalizedItem)) == 0
        scan = db.scalar(select(ScanJob))
        run_terminal = db.scalar(
            select(AgentAction).where(
                AgentAction.tool_name == "run_project",
                AgentAction.event_status == "denied",
            )
        )
    assert scan is not None
    assert scan.status == "failed"
    assert run_terminal is not None
    assert run_terminal.error_code == "session_state_error"


def test_run_recovers_crash_after_action_reservation_before_scan(client) -> None:
    del client
    session_id = _persist_session()
    created = _call(
        session_id,
        "create_project",
        key="create-before-pre-scan-crash-0001",
        expected_version=1,
        arguments={
            "name": "Pre-scan crash recovery",
            "source_type": "fixture",
            "query": "workflow",
        },
    )
    project_id = created["result"]["project_id"]
    key = "recover-pre-scan-crash-0001"
    claim, _request = _reserve_run_without_mutation(
        session_id,
        key=key,
        project_id=project_id,
    )

    recovered = _call(
        session_id,
        "run_project",
        key=key,
        expected_version=1,
        arguments={"project_id": project_id},
    )

    assert recovered["ok"] is True, recovered
    assert recovered["outcome"] == "replay"
    assert recovered["result"]["status"] == "completed"
    assert recovered["result"]["id"] == str(claim.correlation_id)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ScanJob)) == 1
        events = list(
            db.scalars(
                select(AgentAction)
                .where(AgentAction.operation_id == claim.operation_id)
                .order_by(AgentAction.event_sequence)
            )
        )
    assert [event.event_status for event in events] == [
        "reserved",
        "replayed",
        "succeeded",
    ]


def test_new_process_reuses_committed_scan_and_terminalizes_old_action(client) -> None:
    del client
    session_id = _persist_session()
    created = _call(
        session_id,
        "create_project",
        key="create-before-terminal-crash-0001",
        expected_version=1,
        arguments={
            "name": "Terminal crash recovery",
            "source_type": "fixture",
            "query": "workflow",
        },
    )
    project_id = created["result"]["project_id"]
    key = "recover-terminal-crash-0001"
    claim, _request = _reserve_run_without_mutation(
        session_id,
        key=key,
        project_id=project_id,
    )
    with SessionLocal() as db:
        project = db.get(ResearchProject, UUID(project_id))
        assert project is not None
        committed_scan = scan_pipeline.process_scan(
            db,
            source=project.source_type,
            query=project.query,
            limit=project.limit,
            research_project=project,
            expected_project_version=1,
            scan_id=claim.correlation_id,
        )
    assert committed_scan.status == "completed"

    replacement_secret = "replacement-process-secret-with-at-least-thirty-two-bytes"
    replacement_session_id = _persist_session(raw_secret=replacement_secret)
    recovered = _call(
        replacement_session_id,
        "run_project",
        key=key,
        expected_version=1,
        arguments={"project_id": project_id},
        raw_secret=replacement_secret,
    )

    assert recovered["ok"] is True
    assert recovered["outcome"] == "succeeded"
    assert recovered["result"]["id"] == str(committed_scan.id)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ScanJob)) == 1
        terminal = db.scalar(
            select(AgentAction).where(
                AgentAction.operation_id == claim.operation_id,
                AgentAction.event_status == "succeeded",
            )
        )
    assert terminal is not None


def test_new_process_closes_stale_running_scan_after_owner_expiry(client) -> None:
    del client
    original_session_id = _persist_session()
    created = _call(
        original_session_id,
        "create_project",
        key="create-before-stale-running-scan-0001",
        expected_version=1,
        arguments={
            "name": "Stale running scan recovery",
            "source_type": "fixture",
            "query": "workflow",
        },
    )
    project_id = created["result"]["project_id"]
    key = "recover-stale-running-scan-0001"
    claim, _request = _reserve_run_without_mutation(
        original_session_id,
        key=key,
        project_id=project_id,
    )
    with SessionLocal() as db:
        project = db.get(ResearchProject, UUID(project_id))
        assert project is not None
        scan, _run = scan_pipeline.reserve_scan_job(
            db,
            source_type=project.source_type,
            query=project.query,
            requested_limit=project.limit,
            research_project_id=project.id,
            expected_project_version=1,
            scan_id=claim.correlation_id,
        )
        scan.status = "running"
        scan.started_at = datetime.now(UTC)
        owner = db.get(AgentSession, original_session_id)
        assert owner is not None
        owner.status = "expired"
        owner.expired_at = datetime.now(UTC)
        owner.version += 1
        db.commit()

    replacement_secret = "stale-scan-replacement-secret-with-at-least-thirty-two-bytes"
    replacement_session_id = _persist_session(raw_secret=replacement_secret)
    recovered = _call(
        replacement_session_id,
        "run_project",
        key=key,
        expected_version=1,
        arguments={"project_id": project_id},
        raw_secret=replacement_secret,
    )
    replay = _call(
        replacement_session_id,
        "run_project",
        key=key,
        expected_version=1,
        arguments={"project_id": project_id},
        raw_secret=replacement_secret,
    )

    assert recovered["ok"] is True, recovered
    assert recovered["result"]["status"] == "failed"
    assert replay["outcome"] == "replay"
    assert replay["result"] == recovered["result"]
    with SessionLocal() as db:
        scan = db.get(ScanJob, claim.correlation_id)
        terminal_count = db.scalar(
            select(func.count()).select_from(AgentAction).where(
                AgentAction.correlation_id == claim.correlation_id,
                AgentAction.event_status.in_(("succeeded", "failed", "denied")),
            )
        )
    assert scan is not None
    assert scan.status == "failed"
    assert scan.items_saved == 0
    assert terminal_count == 2


def test_agent_decision_and_label_persist_session_provenance(client) -> None:
    session_id = _persist_session()
    demo = client.post("/api/v1/process/demo")
    assert demo.status_code == 200, demo.text
    thread = client.get("/api/v1/opportunity-threads").json()[0]
    item = thread["current_snapshot"]["evidence_items"][0]

    decision = _call(
        session_id,
        "set_opportunity_decision",
        key="decision-write-surface-0001",
        expected_version=thread["version"],
        arguments={
            "thread_id": thread["id"],
            "review_state": "build_candidate",
            "review_note": "private agent note",
        },
    )
    label = _call(
        session_id,
        "append_evidence_label",
        key="label-write-surface-0001",
        expected_version=0,
        arguments={
            "item_id": item["id"],
            "label": "true_signal",
            "user_note": "private agent label note",
        },
    )

    assert decision["ok"] is True
    assert decision["result"]["review_state"] == "build_candidate"
    assert label["ok"] is True
    assert label["result"]["version"] == 1
    with SessionLocal() as db:
        decision_event = db.scalar(
            select(OpportunityDecisionEvent)
            .where(OpportunityDecisionEvent.actor_type == "agent")
            .order_by(OpportunityDecisionEvent.created_at.desc())
        )
        saved_label = db.scalar(
            select(Label)
            .where(Label.item_id == UUID(item["id"]))
            .order_by(Label.version.desc())
        )
    assert decision_event is not None
    assert decision_event.agent_session_id == session_id
    assert decision_event.next_note == "private agent note"
    assert saved_label is not None
    assert saved_label.actor_type == "agent"
    assert saved_label.agent_session_id == session_id
    assert saved_label.user_note == "private agent label note"
    assert "private" not in json.dumps([decision, label], sort_keys=True).lower()


def test_deterministic_build_packet_is_created_once_from_ready_candidate(client) -> None:
    session_id = _persist_session()
    demo = client.post("/api/v1/process/demo")
    assert demo.status_code == 200, demo.text
    thread = client.get("/api/v1/opportunity-threads").json()[0]

    blocked = _call(
        session_id,
        "create_build_packet",
        key="packet-before-candidate-surface-0001",
        expected_version=thread["version"],
        arguments={"thread_id": thread["id"]},
    )
    assert blocked["error"] == {
        "code": "not_ready",
        "reason": "build_candidate_required",
    }

    decision = _call(
        session_id,
        "set_opportunity_decision",
        key="packet-candidate-decision-surface-0001",
        expected_version=thread["version"],
        arguments={
            "thread_id": thread["id"],
            "review_state": "build_candidate",
        },
    )
    assert decision["ok"] is True
    packet_arguments = {"thread_id": thread["id"], "use_configured_ai": False}
    created = _call(
        session_id,
        "create_build_packet",
        key="create-packet-write-surface-0001",
        expected_version=decision["result"]["version"],
        arguments=packet_arguments,
    )
    replay = _call(
        session_id,
        "create_build_packet",
        key="create-packet-write-surface-0001",
        expected_version=decision["result"]["version"],
        arguments=packet_arguments,
    )

    assert created["ok"] is True
    assert created["result"]["generation_mode"] == "deterministic"
    assert created["result"]["enhancement_status"] == "not_requested"
    assert created["result"]["artifact_count"] == 10
    assert replay["ok"] is True
    assert replay["result"] == created["result"]
    with SessionLocal() as db:
        packets = list(db.scalars(select(BuildPacket)))
    assert len(packets) == 1
    assert len(packets[0].artifacts_json) == 9
    assert packets[0].manifest_json["file_count"] == 10
    serialized = json.dumps(packets[0].source_snapshot_json, sort_keys=True)
    assert "review_note" not in serialized
    assert "user_note" not in serialized


def test_invalid_and_not_found_requests_are_structured_and_audited(client) -> None:
    del client
    session_id = _persist_session()
    invalid = _call(
        session_id,
        "create_project",
        key="invalid-project-write-surface-0001",
        expected_version=1,
        arguments={
            "name": "Project",
            "source_type": "fixture",
            "query": "workflow",
            "arbitrary_url": "https://127.0.0.1/private?secret=value",
        },
    )
    missing = _call(
        session_id,
        "update_project",
        key="missing-project-write-surface-0001",
        expected_version=1,
        arguments={"project_id": str(uuid4()), "name": "Missing"},
    )

    assert invalid["error"] == {"code": "invalid_request"}
    assert missing["error"] == {"code": "not_found", "resource": "research_project"}
    serialized = json.dumps([invalid, missing], sort_keys=True)
    assert "127.0.0.1" not in serialized
    assert "secret" not in serialized
    with SessionLocal() as db:
        terminal = list(
            db.scalars(
                select(AgentAction)
                .where(AgentAction.event_status.in_(("denied", "failed")))
                .order_by(AgentAction.created_at)
            )
        )
    assert [(event.event_status, event.error_code) for event in terminal] == [
        ("denied", "invalid_request"),
        ("failed", "not_found"),
    ]


def test_ai_packet_capability_is_checked_by_audited_executor(client) -> None:
    del client
    session_id = _persist_session(configured_ai=False)
    denied = _call(
        session_id,
        "create_build_packet",
        key="ai-packet-write-surface-0001",
        expected_version=1,
        arguments={"thread_id": str(uuid4()), "use_configured_ai": True},
    )

    assert denied["ok"] is False
    assert denied["outcome"] == "error"
    assert denied["error"] == {"code": "session_capability_error"}
    with SessionLocal() as db:
        actions = list(
            db.scalars(select(AgentAction).order_by(AgentAction.event_sequence))
        )
        assert [action.event_status for action in actions] == ["reserved", "denied"]
        assert actions[-1].error_code == "session_capability_error"
        assert actions[-1].request_summary_json["use_configured_ai"] is True
        assert actions[-1].request_summary_json["generation_mode"] == "configured_ai"
        assert db.scalar(select(func.count()).select_from(NormalizedItem)) == 0


def test_pending_session_denial_is_structured_and_not_audited(client) -> None:
    del client
    session_id = _persist_pending_session()
    denied = _call(
        session_id,
        "create_project",
        key="pending-session-write-surface-0001",
        expected_version=1,
        arguments={
            "name": "Pending must not write",
            "source_type": "fixture",
            "query": "workflow",
        },
    )

    assert denied["error"] == {"code": "session_state_error"}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AgentAction)) == 0
        assert db.scalar(select(func.count()).select_from(ResearchProject)) == 0


def test_approved_ai_capability_adds_only_fixed_enhanced_variants(
    client,
    monkeypatch,
) -> None:
    session_id = _persist_session(configured_ai=True)
    assert client.post("/api/v1/process/demo").status_code == 200
    thread = client.get("/api/v1/opportunity-threads").json()[0]
    decision = _call(
        session_id,
        "set_opportunity_decision",
        key="ai-packet-candidate-decision-0001",
        expected_version=thread["version"],
        arguments={
            "thread_id": thread["id"],
            "review_state": "build_candidate",
        },
    )

    prompts: list[str] = []

    def enhance(prompt: str):
        prompts.append(prompt)
        return (
            "ollama",
            "local-test-model",
            json.dumps(
                {
                    name: f"# Enhanced {name}\n\nBounded agent guidance."
                    for name in ENHANCEABLE_FILENAMES
                }
            ),
        )

    monkeypatch.setattr(mcp_writes, "enhance_prompt", enhance)
    created = _call(
        session_id,
        "create_build_packet",
        key="ai-packet-write-surface-0002",
        expected_version=decision["result"]["version"],
        arguments={"thread_id": thread["id"], "use_configured_ai": True},
    )

    assert created["ok"] is True
    assert created["result"]["generation_mode"] == "configured_ai"
    assert created["result"]["enhancement_status"] == "generated"
    assert created["result"]["artifact_count"] == 16
    assert len(prompts) == 1
    with SessionLocal() as db:
        packet = db.scalar(select(BuildPacket))
    assert packet is not None
    assert set(packet.enhanced_artifacts_json or {}) == {
        f"enhanced/{name}" for name in ENHANCEABLE_FILENAMES
    }


def test_revoke_during_ai_generation_blocks_packet_persistence(
    client,
    monkeypatch,
) -> None:
    session_id = _persist_session(configured_ai=True)
    assert client.post("/api/v1/process/demo").status_code == 200
    thread = client.get("/api/v1/opportunity-threads").json()[0]
    decision = _call(
        session_id,
        "set_opportunity_decision",
        key="revoked-ai-candidate-decision-0001",
        expected_version=thread["version"],
        arguments={
            "thread_id": thread["id"],
            "review_state": "build_candidate",
        },
    )
    entered_provider = threading.Event()
    release_provider = threading.Event()

    def enhance(_prompt: str):
        entered_provider.set()
        assert release_provider.wait(timeout=10)
        return (
            "ollama",
            "local-test-model",
            json.dumps(
                {
                    name: f"# Enhanced {name}\n\nBounded agent guidance."
                    for name in ENHANCEABLE_FILENAMES
                }
            ),
        )

    monkeypatch.setattr(mcp_writes, "enhance_prompt", enhance)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _call,
            session_id,
            "create_build_packet",
            key="revoked-ai-packet-write-0001",
            expected_version=decision["result"]["version"],
            arguments={"thread_id": thread["id"], "use_configured_ai": True},
        )
        assert entered_provider.wait(timeout=10)
        with SessionLocal() as db:
            session = db.get(AgentSession, session_id)
            assert session is not None
            revoke_session(session, expected_version=session.version)
            db.commit()
        release_provider.set()
        denied = future.result(timeout=10)

    assert denied["ok"] is False
    assert denied["error"] == {"code": "session_state_error"}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BuildPacket)) == 0
        denied_action = db.scalar(
            select(AgentAction).where(
                AgentAction.tool_name == "create_build_packet",
                AgentAction.event_status == "denied",
            )
        )
    assert denied_action is not None
    assert denied_action.error_code == "session_state_error"


def test_replacement_process_never_repeats_indeterminate_ai_provider_call(
    client,
    monkeypatch,
) -> None:
    original_session_id = _persist_session(configured_ai=True)
    assert client.post("/api/v1/process/demo").status_code == 200
    thread = client.get("/api/v1/opportunity-threads").json()[0]
    decision = _call(
        original_session_id,
        "set_opportunity_decision",
        key="indeterminate-ai-candidate-decision-0001",
        expected_version=thread["version"],
        arguments={"thread_id": thread["id"], "review_state": "build_candidate"},
    )
    key = "indeterminate-ai-packet-0001"
    request = {
        "thread_id": thread["id"],
        "expected_version": decision["result"]["version"],
        "use_configured_ai": True,
        "generation_mode": "configured_ai",
    }
    correlation_id = mcp_writes._configured_ai_packet_correlation_id(key, request)
    with SessionLocal() as db:
        claim = _authorize_and_reserve_agent_action(
            db,
            session_id=original_session_id,
            raw_session_secret=RAW_SECRET,
            tool_name="create_build_packet",
            idempotency_key=key,
            request=request,
            correlation_id=correlation_id,
        )
        db.commit()
    assert claim.outcome == "reserved"

    provider_calls = 0

    def must_not_call_provider(_prompt: str):
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("replacement process repeated an indeterminate provider call")

    monkeypatch.setattr(mcp_writes, "enhance_prompt", must_not_call_provider)
    replacement_secret = "indeterminate-ai-replacement-secret-at-least-thirty-two-bytes"
    replacement_session_id = _persist_session(
        configured_ai=True,
        raw_secret=replacement_secret,
    )
    arguments = {"thread_id": thread["id"], "use_configured_ai": True}
    active = _call(
        replacement_session_id,
        "create_build_packet",
        key=key,
        expected_version=decision["result"]["version"],
        arguments=arguments,
        raw_secret=replacement_secret,
    )
    assert active["outcome"] == "in_progress"

    with SessionLocal() as db:
        owner = db.get(AgentSession, original_session_id)
        assert owner is not None
        owner.status = "expired"
        owner.expired_at = datetime.now(UTC)
        owner.version += 1
        db.commit()

    indeterminate = _call(
        replacement_session_id,
        "create_build_packet",
        key=key,
        expected_version=decision["result"]["version"],
        arguments=arguments,
        raw_secret=replacement_secret,
    )
    replay = _call(
        replacement_session_id,
        "create_build_packet",
        key=key,
        expected_version=decision["result"]["version"],
        arguments=arguments,
        raw_secret=replacement_secret,
    )

    assert provider_calls == 0
    assert indeterminate["outcome"] == "replay"
    assert indeterminate["error"] == {"code": "external_effect_indeterminate"}
    assert replay["error"] == indeterminate["error"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BuildPacket)) == 0
        terminal_count = db.scalar(
            select(func.count()).select_from(AgentAction).where(
                AgentAction.correlation_id == correlation_id,
                AgentAction.event_status == "failed",
                AgentAction.error_code == "external_effect_indeterminate",
            )
        )
    assert terminal_count == 2


def test_concurrent_ai_reservations_elect_one_provider_owner(
    client,
    monkeypatch,
) -> None:
    first_session_id = _persist_session(configured_ai=True)
    second_secret = "second-ai-process-secret-with-at-least-thirty-two-bytes"
    second_session_id = _persist_session(
        configured_ai=True,
        raw_secret=second_secret,
    )
    assert client.post("/api/v1/process/demo").status_code == 200
    thread = client.get("/api/v1/opportunity-threads").json()[0]
    decision = _call(
        first_session_id,
        "set_opportunity_decision",
        key="concurrent-ai-candidate-decision-0001",
        expected_version=thread["version"],
        arguments={"thread_id": thread["id"], "review_state": "build_candidate"},
    )
    key = "concurrent-ai-packet-0001"
    expected_version = decision["result"]["version"]
    provider_calls = 0
    entered_provider = threading.Event()
    release_provider = threading.Event()

    def enhance(_prompt: str):
        nonlocal provider_calls
        provider_calls += 1
        entered_provider.set()
        assert release_provider.wait(timeout=10)
        return (
            "ollama",
            "local-test-model",
            json.dumps(
                {
                    name: f"# Enhanced {name}\n\nSingle-owner guidance."
                    for name in ENHANCEABLE_FILENAMES
                }
            ),
        )

    monkeypatch.setattr(mcp_writes, "enhance_prompt", enhance)

    def create(session_id, raw_secret):
        return _call(
            session_id,
            "create_build_packet",
            key=key,
            expected_version=expected_version,
            arguments={"thread_id": thread["id"], "use_configured_ai": True},
            raw_secret=raw_secret,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        first_future = executor.submit(create, first_session_id, RAW_SECRET)
        assert entered_provider.wait(timeout=10)
        second = create(second_session_id, second_secret)
        release_provider.set()
        first = first_future.result(timeout=15)

    assert provider_calls == 1
    assert first["ok"] is True
    assert second["outcome"] == "in_progress"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(BuildPacket)) == 1

    first_replay = create(first_session_id, RAW_SECRET)
    second_replay = create(second_session_id, second_secret)
    assert first_replay["ok"] is True
    assert second_replay["ok"] is True
    assert first_replay["result"]["packet_id"] == second_replay["result"]["packet_id"]
