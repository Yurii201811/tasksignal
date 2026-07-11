from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import select

import app.services.agent_actions.executor as action_executor
from app.db.session import SessionLocal
from app.models.all_models import AgentAction, AgentSession, ResearchProject
from app.services.agent_actions import execute_audited_agent_action
from app.services.agent_sessions import (
    STANDARD_WRITE_CAPABILITIES,
    SessionStateError,
    hash_session_secret,
)
from app.workers.scan_pipeline import (
    SCAN_WRITE_LOCK,
    acquire_database_scan_write_lock_with_retry,
)

RAW_SECRET = "durable-agent-action-secret-with-at-least-thirty-two-bytes"


class DomainWriteFailed(RuntimeError):
    pass


def _approved_session() -> AgentSession:
    now = datetime.now(UTC)
    return AgentSession(
        process_instance_id=uuid4(),
        client_name="Durable executor test",
        client_version="1.0",
        transport="stdio",
        secret_hash=hash_session_secret(RAW_SECRET),
        status="approved",
        requested_capabilities_json=sorted(STANDARD_WRITE_CAPABILITIES),
        approved_capabilities_json=sorted(STANDARD_WRITE_CAPABILITIES),
        approval_source="ui",
        approved_at=now,
        last_heartbeat_at=now,
        expires_at=now + timedelta(minutes=5),
        version=2,
        created_at=now,
        updated_at=now,
    )


def test_domain_rollback_cannot_erase_reserved_and_failed_audit(client) -> None:
    del client  # Provides a clean schema for the global SessionLocal factory.
    with SessionLocal() as db:
        session = _approved_session()
        db.add(session)
        db.commit()
        session_id = session.id

    def mutation(db):
        db.add(
            ResearchProject(
                name="Must roll back",
                source_type="fixture",
                query="private query",
                limit=10,
                cadence="manual",
                labels_json=[],
                enabled=True,
                version=1,
            )
        )
        db.flush()
        raise DomainWriteFailed("private failure detail")

    with pytest.raises(DomainWriteFailed, match="private failure detail"):
        execute_audited_agent_action(
            SessionLocal,
            session_id=session_id,
            raw_session_secret=RAW_SECRET,
            tool_name="create_project",
            idempotency_key="durable-create-project-failure-0001",
            request={
                "expected_version": 1,
                "source_type": "fixture",
                "query": "private query",
            },
            mutation=mutation,
        )

    with SessionLocal() as db:
        actions = list(db.scalars(select(AgentAction).order_by(AgentAction.event_sequence)))
        projects = list(db.scalars(select(ResearchProject)))
    assert projects == []
    assert [event.event_status for event in actions] == ["reserved", "failed"]
    assert actions[1].error_code == "domain_write_failed"
    assert "private" not in str(actions[1].result_summary_json)


def test_success_is_durable_and_identical_retry_replays_without_mutation(client) -> None:
    del client
    with SessionLocal() as db:
        session = _approved_session()
        db.add(session)
        db.commit()
        session_id = session.id

    calls = 0

    def mutation(db):
        nonlocal calls
        calls += 1
        project = ResearchProject(
            name="Created once",
            source_type="fixture",
            query="workflow",
            limit=10,
            cadence="manual",
            labels_json=[],
            enabled=True,
            version=1,
        )
        db.add(project)
        db.flush()
        return {
            "id": project.id,
            "project_id": project.id,
            "version": project.version,
            "status": "created",
        }

    arguments = {
        "session_id": session_id,
        "raw_session_secret": RAW_SECRET,
        "tool_name": "create_project",
        "idempotency_key": "durable-create-project-success-0001",
        "request": {
            "expected_version": 1,
            "source_type": "fixture",
            "query": "workflow",
        },
        "mutation": mutation,
    }
    first = execute_audited_agent_action(SessionLocal, **arguments)
    replay = execute_audited_agent_action(SessionLocal, **arguments)

    assert first.outcome == "succeeded"
    assert replay.outcome == "replay"
    assert replay.result == {
        "id": str(first.result["id"]),
        "project_id": str(first.result["project_id"]),
        "status": "created",
        "version": 1,
    }
    assert calls == 1
    with SessionLocal() as db:
        actions = list(db.scalars(select(AgentAction).order_by(AgentAction.event_sequence)))
        projects = list(db.scalars(select(ResearchProject)))
    assert len(projects) == 1
    assert [event.event_status for event in actions] == [
        "reserved",
        "succeeded",
        "replayed",
    ]


def test_expired_authorization_is_materialized_without_an_action(client) -> None:
    del client
    now = datetime.now(UTC)
    with SessionLocal() as db:
        session = _approved_session()
        session.last_heartbeat_at = now - timedelta(minutes=2)
        session.expires_at = now - timedelta(minutes=1)
        db.add(session)
        db.commit()
        session_id = session.id

    with pytest.raises(SessionStateError, match="expired"):
        execute_audited_agent_action(
            SessionLocal,
            session_id=session_id,
            raw_session_secret=RAW_SECRET,
            tool_name="run_project",
            idempotency_key="durable-expired-session-0001",
            request={"project_id": uuid4(), "expected_version": 1},
            mutation=lambda _db: None,
        )

    with SessionLocal() as db:
        session = db.get(AgentSession, session_id)
        actions = list(db.scalars(select(AgentAction)))
    assert session is not None
    assert session.status == "expired"
    assert session.expired_at is not None
    assert actions == []


def test_success_audit_failure_rolls_back_domain_write(client, monkeypatch) -> None:
    del client
    with SessionLocal() as db:
        session = _approved_session()
        db.add(session)
        db.commit()
        session_id = session.id

    def reject_success_audit(*_args, **_kwargs):
        raise RuntimeError("simulated terminal audit failure")

    monkeypatch.setattr(action_executor, "complete_agent_action", reject_success_audit)

    def mutation(db):
        project = ResearchProject(
            name="Must remain atomic",
            source_type="fixture",
            query="workflow",
            limit=10,
            cadence="manual",
            labels_json=[],
            enabled=True,
            version=1,
        )
        db.add(project)
        db.flush()
        return {"project_id": project.id, "version": 1}

    with pytest.raises(RuntimeError, match="terminal audit failure"):
        execute_audited_agent_action(
            SessionLocal,
            session_id=session_id,
            raw_session_secret=RAW_SECRET,
            tool_name="create_project",
            idempotency_key="durable-terminal-failure-0001",
            request={"expected_version": 1, "source_type": "fixture"},
            mutation=mutation,
        )

    with SessionLocal() as db:
        projects = list(db.scalars(select(ResearchProject)))
        actions = list(db.scalars(select(AgentAction).order_by(AgentAction.event_sequence)))
    assert projects == []
    assert [event.event_status for event in actions] == ["reserved", "failed"]


def test_long_mutation_does_not_hold_process_lock_after_releasing_database(client) -> None:
    del client
    with SessionLocal() as db:
        session = _approved_session()
        db.add(session)
        db.commit()
        session_id = session.id

    mutation_started = Event()
    release_mutation = Event()
    concurrent_write_finished = Event()

    def mutation(db):
        db.rollback()
        mutation_started.set()
        assert release_mutation.wait(timeout=2)
        acquire_database_scan_write_lock_with_retry(db)
        project = ResearchProject(
            name="Long mutation",
            source_type="fixture",
            query="workflow",
            limit=10,
            cadence="manual",
            labels_json=[],
            enabled=True,
            version=1,
        )
        db.add(project)
        db.flush()
        return {"project_id": project.id, "version": 1}

    def execute_long_mutation():
        return execute_audited_agent_action(
            SessionLocal,
            session_id=session_id,
            raw_session_secret=RAW_SECRET,
            tool_name="create_project",
            idempotency_key="durable-long-mutation-0001",
            request={"expected_version": 1, "source_type": "fixture"},
            mutation=mutation,
        )

    def concurrent_write_probe() -> None:
        with SCAN_WRITE_LOCK, SessionLocal() as db:
            acquire_database_scan_write_lock_with_retry(db)
            db.rollback()
        concurrent_write_finished.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        action_future = pool.submit(execute_long_mutation)
        assert mutation_started.wait(timeout=2)
        probe_future = pool.submit(concurrent_write_probe)
        probe_finished_before_release = concurrent_write_finished.wait(timeout=1)
        release_mutation.set()
        probe_future.result(timeout=2)
        execution = action_future.result(timeout=2)

    assert probe_finished_before_release is True
    assert execution.outcome == "succeeded"
