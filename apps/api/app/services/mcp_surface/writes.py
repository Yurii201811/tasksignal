"""Guarded, SDK-independent MCP writes for the fixed v1 tool surface."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.version import TASKSIGNAL_VERSION
from app.models.all_models import (
    AgentAction,
    AgentSession,
    BuildPacket,
    Cluster,
    ClusterItem,
    DiscourseSourceState,
    ItemSignal,
    NormalizedItem,
    Opportunity,
    OpportunityDecisionEvent,
    OpportunityThread,
    ResearchProject,
    ResearchProjectRun,
    ScanItem,
    ScanJob,
    Source,
)
from app.services.agent_actions import (
    IDEMPOTENCY_REPLAY,
    AgentActionExecution,
    AgentActionServiceError,
    canonical_request_hash,
    execute_audited_agent_action,
)
from app.services.agent_actions.service import (
    ActionClaim,
    InvalidActionTransition,
    _authorize_agent_action_session,
    _core_terminal_event,
    complete_agent_action,
    fail_agent_action,
    summarize_result,
)
from app.services.agent_sessions import AgentSessionError, expire_session_if_needed
from app.services.build_packets import (
    BUILD_PACKET_SCHEMA_VERSION,
    BUILD_PACKET_TEMPLATE_VERSION,
    BuildPacketMetadata,
    build_packet_artifacts,
    redact_public_text,
    safe_public_source_url,
    verify_packet_artifacts,
)
from app.services.build_packets.enhancement import (
    ENHANCEMENT_TEMPLATE_VERSION,
    InvalidBuildPacketEnhancement,
    build_enhancement_prompt,
    manifest_with_enhancement,
    parse_enhanced_documents,
)
from app.services.discourse_sources.service import discourse_readiness
from app.services.evidence_review.service import (
    EvidenceLabelVersionConflict,
    append_evidence_label,
    calculate_evidence_readiness,
    get_agent_review_snapshots,
    get_review_snapshots,
    unresolved_sensitive_risk,
)
from app.services.evidence_review.types import (
    EvidenceReadinessLevel,
    EvidenceReviewLabel,
    ReviewState,
)
from app.services.generation.enhancement import (
    EnhancementUnavailable,
    configured_provider,
    enhance_prompt,
)
from app.services.opportunity_threads.service import (
    ThreadVersionConflict,
    set_thread_decision,
)
from app.services.research_projects.service import mark_latest_project_run, next_run_at_from
from app.workers.scan_pipeline import (
    CONNECTOR_FACTORIES,
    ProjectVersionConflict,
    acquire_database_scan_write_lock_with_retry,
    canonical_source,
    process_scan,
)

SessionFactory = Callable[[], Session]

MCP_WRITE_OPERATIONS = frozenset(
    {
        "create_project",
        "update_project",
        "run_project",
        "set_opportunity_decision",
        "append_evidence_label",
        "create_build_packet",
    }
)

__all__ = ["MCP_WRITE_OPERATIONS", "MCPWriteDomainError", "execute_mcp_write"]


class MCPWriteDomainError(RuntimeError):
    """A public, redacted domain failure that is safe for MCP and audit output."""

    def __init__(
        self,
        code: str,
        *,
        details: Mapping[str, Any] | None = None,
        denied: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.details = dict(details or {})
        self.denied = denied


class _WriteModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _CreateProject(_WriteModel):
    expected_version: Literal[1]
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    source_type: str = Field(default="hackernews", min_length=1, max_length=60)
    source_id: UUID | None = None
    query: str = Field(default="", max_length=300)
    limit: int = Field(default=30, ge=1, le=100)
    cadence: str = Field(default="manual", min_length=1, max_length=60)
    schedule_interval_hours: int | None = Field(default=None, ge=1, le=24 * 31)
    labels: list[str] = Field(default_factory=list, max_length=12)
    enabled: bool = True


class _UpdateProject(_WriteModel):
    project_id: UUID
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    source_type: str | None = Field(default=None, min_length=1, max_length=60)
    source_id: UUID | None = None
    query: str | None = Field(default=None, max_length=300)
    limit: int | None = Field(default=None, ge=1, le=100)
    cadence: str | None = Field(default=None, min_length=1, max_length=60)
    schedule_interval_hours: int | None = Field(default=None, ge=1, le=24 * 31)
    labels: list[str] | None = Field(default=None, max_length=12)
    enabled: bool | None = None


class _RunProject(_WriteModel):
    project_id: UUID
    expected_version: int = Field(ge=1)
    limit: int | None = Field(default=None, ge=1, le=100)


class _SetOpportunityDecision(_WriteModel):
    thread_id: UUID
    expected_version: int = Field(ge=1)
    review_state: ReviewState
    review_note: str | None = Field(default=None, max_length=1000)


class _AppendEvidenceLabel(_WriteModel):
    item_id: UUID
    expected_version: int = Field(ge=0)
    label: EvidenceReviewLabel
    user_note: str | None = Field(default=None, max_length=500)


class _CreateBuildPacket(_WriteModel):
    thread_id: UUID
    expected_version: int = Field(ge=1)
    use_configured_ai: bool = False
    generation_mode: Literal["deterministic", "configured_ai"]

    @model_validator(mode="after")
    def matching_generation_mode(self) -> _CreateBuildPacket:
        expected = "configured_ai" if self.use_configured_ai else "deterministic"
        if self.generation_mode != expected:
            raise ValueError("generation_mode does not match use_configured_ai")
        return self


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _utc(value).astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): _json_safe(entry) for key, entry in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(entry) for entry in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return None


def _error_for_exception(exc: Exception) -> tuple[str, dict[str, Any], bool]:
    if isinstance(exc, MCPWriteDomainError):
        return exc.code, dict(exc.details), exc.denied
    if isinstance(exc, ValidationError):
        return "invalid_request", {}, True
    if isinstance(exc, EvidenceLabelVersionConflict):
        return (
            "version_conflict",
            {
                "expected_version": exc.expected_version,
                "current_version": exc.current_version,
            },
            False,
        )
    if isinstance(exc, ThreadVersionConflict):
        return "version_conflict", {}, False
    if isinstance(exc, ProjectVersionConflict):
        return "version_conflict", {}, False
    if isinstance(exc, AgentSessionError):
        return exc.code, {}, True
    if isinstance(exc, AgentActionServiceError):
        return exc.code, {}, True
    if isinstance(exc, IntegrityError):
        return "domain_conflict", {}, False
    return "internal_error", {}, False


def _failure_mapper(
    exc: Exception,
) -> tuple[Literal["failed", "denied", "in_progress"], str, Mapping[str, Any]]:
    code, details, denied = _error_for_exception(exc)
    if code == "idempotency_in_progress":
        return "in_progress", code, details
    return ("denied" if denied else "failed"), code, details


def _public_error(exc: Exception) -> dict[str, Any]:
    code, details, _denied = _error_for_exception(exc)
    return {"code": code, **_json_safe(details)}


def _result_envelope(execution: AgentActionExecution) -> dict[str, Any]:
    base = {
        "operation_id": str(execution.operation_id),
        "correlation_id": str(execution.correlation_id),
    }
    if execution.outcome == "succeeded":
        return {
            "ok": True,
            "outcome": "succeeded",
            **base,
            "result": _json_safe(execution.result),
            "error": None,
        }
    if execution.outcome == "replay":
        successful_replay = execution.error_code == IDEMPOTENCY_REPLAY
        replay_result = _json_safe(execution.result)
        return {
            "ok": successful_replay,
            "outcome": "replay",
            **base,
            "result": replay_result if successful_replay else None,
            "error": (
                None
                if successful_replay
                else {
                    "code": execution.error_code or "replayed_failure",
                    **(replay_result if isinstance(replay_result, dict) else {}),
                }
            ),
        }
    return {
        "ok": False,
        "outcome": execution.outcome,
        **base,
        "result": _json_safe(execution.result),
        "error": {"code": execution.error_code or f"idempotency_{execution.outcome}"},
    }


def _version_conflict(expected: int, current: int) -> MCPWriteDomainError:
    return MCPWriteDomainError(
        "version_conflict",
        details={"expected_version": expected, "current_version": current},
    )


def _not_found(resource: str) -> MCPWriteDomainError:
    return MCPWriteDomainError("not_found", details={"resource": resource})


def _not_ready(reason: str) -> MCPWriteDomainError:
    return MCPWriteDomainError("not_ready", details={"reason": reason})


def _invalid_request() -> MCPWriteDomainError:
    return MCPWriteDomainError("invalid_request", denied=True)


def _validate_labels(labels: list[str]) -> list[str]:
    normalized: list[str] = []
    for label in labels:
        if not isinstance(label, str):
            raise _invalid_request()
        clean = label.strip()
        if len(clean) > 80:
            raise _invalid_request()
        if clean and clean not in normalized:
            normalized.append(clean)
    return normalized[:12]


def _validate_source_binding(
    db: Session,
    *,
    source_type: str,
    source_id: UUID | None,
) -> Source | None:
    if source_type not in CONNECTOR_FACTORIES:
        raise _invalid_request()
    if source_type == "discourse" and source_id is None:
        raise _not_ready("authorized_source_required")
    if source_id is None:
        return None
    source = db.get(Source, source_id)
    if source is None:
        raise _not_found("source")
    if canonical_source(source.type) != source_type:
        raise MCPWriteDomainError("domain_conflict", details={"resource": "source"})
    if not source.enabled:
        raise _not_ready("source_disabled")
    if source_type == "discourse":
        state = db.get(DiscourseSourceState, source.id)
        if (
            state is None
            or state.authorized_at is None
            or state.terms_confirmed_at is None
        ):
            raise _not_ready("source_terms_not_authorized")
    return source


def _project_result(project: ResearchProject, status: str) -> dict[str, Any]:
    return {
        "id": project.id,
        "project_id": project.id,
        "version": project.version,
        "source_type": redact_public_text(project.source_type),
        "cadence": redact_public_text(project.cadence),
        "enabled": project.enabled,
        "status": status,
    }


def _run_scan_id(idempotency_key: str, request: Mapping[str, Any]) -> UUID:
    """Derive a process-independent scan identity for exact crash recovery."""

    if not isinstance(idempotency_key, str):
        return uuid4()
    request_hash = canonical_request_hash("run_project", request)
    digest = hashlib.sha256(
        b"tasksignal:mcp-run-scan:v1\0"
        + request_hash.encode()
        + b"\0"
        + idempotency_key.encode()
    ).digest()
    return UUID(bytes=digest[:16], version=5)


def _configured_ai_packet_correlation_id(
    idempotency_key: str,
    request: Mapping[str, Any],
) -> UUID:
    """Derive a cross-process key that prevents ambiguous paid-I/O retries."""

    if not isinstance(idempotency_key, str):
        return uuid4()
    request_hash = canonical_request_hash("create_build_packet", request)
    digest = hashlib.sha256(
        b"tasksignal:mcp-ai-packet:v1\0"
        + request_hash.encode()
        + b"\0"
        + idempotency_key.encode()
    ).digest()
    return UUID(bytes=digest[:16], version=5)


def _create_project(db: Session, request: Mapping[str, Any]) -> dict[str, Any]:
    payload = _CreateProject.model_validate(request)
    source_type = canonical_source(payload.source_type)
    _validate_source_binding(db, source_type=source_type, source_id=payload.source_id)
    labels = _validate_labels(payload.labels)
    now = datetime.now(UTC)
    project = ResearchProject(
        name=payload.name,
        description=payload.description or None,
        source_type=source_type,
        source_id=payload.source_id,
        query=payload.query,
        limit=payload.limit,
        cadence=payload.cadence,
        schedule_interval_hours=payload.schedule_interval_hours,
        next_run_at=(
            next_run_at_from(now, payload.cadence, payload.schedule_interval_hours)
            if payload.enabled
            else None
        ),
        labels_json=labels,
        enabled=payload.enabled,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.flush()
    return _project_result(project, "created")


def _update_project(db: Session, request: Mapping[str, Any]) -> dict[str, Any]:
    payload = _UpdateProject.model_validate(request)
    project = db.scalar(
        select(ResearchProject)
        .where(ResearchProject.id == payload.project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if project is None:
        raise _not_found("research_project")
    if project.version != payload.expected_version:
        raise _version_conflict(payload.expected_version, project.version)

    supplied = payload.model_fields_set - {"project_id", "expected_version"}
    source_type = (
        canonical_source(payload.source_type or "")
        if "source_type" in supplied
        else project.source_type
    )
    source_id = payload.source_id if "source_id" in supplied else project.source_id
    if (
        "source_type" in supplied
        and "source_id" not in supplied
        and source_type != project.source_type
    ):
        source_id = None
    if supplied & {"source_type", "source_id"}:
        _validate_source_binding(db, source_type=source_type, source_id=source_id)

    if "name" in supplied:
        if payload.name is None:
            raise _invalid_request()
        project.name = payload.name
    if "description" in supplied:
        project.description = payload.description or None
    if "source_type" in supplied:
        project.source_type = source_type
    if supplied & {"source_type", "source_id"}:
        project.source_id = source_id
    if "query" in supplied:
        if payload.query is None:
            raise _invalid_request()
        project.query = payload.query
    if "limit" in supplied:
        if payload.limit is None:
            raise _invalid_request()
        project.limit = payload.limit
    if "cadence" in supplied:
        if payload.cadence is None:
            raise _invalid_request()
        project.cadence = payload.cadence
    if "schedule_interval_hours" in supplied:
        project.schedule_interval_hours = payload.schedule_interval_hours
    if "labels" in supplied:
        if payload.labels is None:
            raise _invalid_request()
        project.labels_json = _validate_labels(payload.labels)
    if "enabled" in supplied:
        if payload.enabled is None:
            raise _invalid_request()
        project.enabled = payload.enabled

    if supplied:
        now = datetime.now(UTC)
        if supplied & {"cadence", "schedule_interval_hours", "enabled"}:
            project.next_run_at = (
                next_run_at_from(
                    now,
                    project.cadence,
                    project.schedule_interval_hours,
                )
                if project.enabled
                else None
            )
        project.updated_at = now
        project.version += 1
        db.flush()
        return _project_result(project, "updated")
    return _project_result(project, "unchanged")


def _run_project(
    db: Session,
    request: Mapping[str, Any],
    *,
    session_id: UUID,
    raw_session_secret: str,
    scan_id: UUID,
) -> dict[str, Any]:
    payload = _RunProject.model_validate(request)
    existing_scan = db.get(ScanJob, scan_id)
    if existing_scan is not None:
        if existing_scan.status not in {"completed", "failed"}:
            raise MCPWriteDomainError(
                "idempotency_in_progress",
                details={"id": scan_id, "status": existing_scan.status},
            )
        return _run_result_for_scan(
            db,
            project_id=payload.project_id,
            scan=existing_scan,
        )
    project = db.scalar(
        select(ResearchProject)
        .where(ResearchProject.id == payload.project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if project is None:
        raise _not_found("research_project")
    if project.version != payload.expected_version:
        raise _version_conflict(payload.expected_version, project.version)
    if not project.enabled:
        raise _not_ready("project_disabled")
    source_type = canonical_source(project.source_type)
    configured_source = _validate_source_binding(
        db,
        source_type=source_type,
        source_id=project.source_id,
    )
    if source_type == "discourse" and configured_source is not None:
        readiness = discourse_readiness(
            configured_source,
            db.get(DiscourseSourceState, configured_source.id),
        )
        if not readiness.can_run:
            raise _not_ready("discourse_source_unavailable")

    # process_scan commits the scan reservation before connector I/O. The action
    # reservation is already durable, so an identical retry cannot reserve a second
    # scan and SQLite does not retain its BEGIN IMMEDIATE lock during the fetch.
    scan = process_scan(
        db,
        source=source_type,
        query=project.query,
        limit=payload.limit or project.limit,
        research_project=project,
        expected_project_version=payload.expected_version,
        scan_id=scan_id,
        before_persist=lambda active_db: _authorize_agent_action_session(
            active_db,
            session_id=session_id,
            raw_session_secret=raw_session_secret,
            tool_name="run_project",
            request=request,
        ),
    )
    # The scan pipeline intentionally commits before and after connector I/O. Re-lock
    # and reauthorize the process lease before the audited terminal event, so revoke,
    # exit, or expiry during the fetch cannot be silently ignored.
    _authorize_agent_action_session(
        db,
        session_id=session_id,
        raw_session_secret=raw_session_secret,
        tool_name="run_project",
        request=request,
    )
    return _run_result_for_scan(db, project_id=payload.project_id, scan=scan)


def _run_result_for_scan(
    db: Session,
    *,
    project_id: UUID,
    scan: ScanJob,
) -> dict[str, Any]:
    research_run = db.scalar(
        select(ResearchProjectRun).where(
            ResearchProjectRun.project_id == project_id,
            ResearchProjectRun.scan_id == scan.id,
        )
    )
    if research_run is None:
        raise MCPWriteDomainError("domain_conflict")
    current_version = db.scalar(
        select(ResearchProject.version).where(ResearchProject.id == project_id)
    )
    if current_version is None:
        raise _not_found("research_project")
    return {
        "id": scan.id,
        "run_id": research_run.id,
        "project_id": project_id,
        "version": current_version,
        "status": scan.status,
        "items_found": scan.items_found,
        "items_saved": scan.items_saved,
        "signals_detected": scan.signals_detected,
        "clusters_created": scan.clusters_created,
        "opportunities_created": scan.opportunities_created,
    }


def _set_opportunity_decision(
    db: Session,
    request: Mapping[str, Any],
    *,
    session_id: UUID,
) -> dict[str, Any]:
    payload = _SetOpportunityDecision.model_validate(request)
    thread = db.scalar(
        select(OpportunityThread)
        .where(OpportunityThread.id == payload.thread_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if thread is None:
        raise _not_found("opportunity_thread")
    if thread.version != payload.expected_version:
        raise _version_conflict(payload.expected_version, thread.version)
    set_thread_decision(
        db,
        thread=thread,
        review_state=payload.review_state.value,
        review_note=payload.review_note,
        expected_version=payload.expected_version,
        actor_type="agent",
        agent_session_id=session_id,
    )
    db.flush()
    return {
        "id": thread.id,
        "thread_id": thread.id,
        "snapshot_id": thread.current_snapshot_id,
        "version": thread.version,
        "review_state": thread.review_state,
        "status": "updated",
    }


def _append_evidence_label(
    db: Session,
    request: Mapping[str, Any],
    *,
    session_id: UUID,
) -> dict[str, Any]:
    payload = _AppendEvidenceLabel.model_validate(request)
    item = db.scalar(
        select(NormalizedItem)
        .where(NormalizedItem.id == payload.item_id)
        .with_for_update()
    )
    if item is None:
        raise _not_found("evidence_item")
    label = append_evidence_label(
        db,
        item_id=payload.item_id,
        label=payload.label,
        user_note=payload.user_note,
        actor_type="agent",
        agent_session_id=session_id,
        expected_version=payload.expected_version,
    )
    db.flush()
    return {
        "id": label.id,
        "item_id": label.item_id,
        "version": label.version,
        "label": label.label,
        "status": "created",
    }


def _canonical_packet_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        separators=(",", ": "),
    ) + "\n"


def _packet_sha256(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _resolve_packet_run(
    db: Session,
    thread: OpportunityThread,
    snapshot: Opportunity,
) -> ResearchProjectRun | None:
    run = db.get(ResearchProjectRun, snapshot.run_id) if snapshot.run_id else None
    if run is None and snapshot.scan_id is not None:
        run = db.scalar(
            select(ResearchProjectRun).where(ResearchProjectRun.scan_id == snapshot.scan_id)
        )
    if run is None:
        cluster = db.get(Cluster, snapshot.cluster_id)
        if cluster is not None and cluster.scan_id is not None:
            run = db.scalar(
                select(ResearchProjectRun).where(
                    ResearchProjectRun.scan_id == cluster.scan_id
                )
            )
    if run is None or thread.project_id is None or run.project_id != thread.project_id:
        return None
    return run


def _evidence_excerpt(item: NormalizedItem, signal: ItemSignal) -> str:
    for span in signal.evidence_spans_json or []:
        cleaned = str(span).replace("\r", " ").replace("\n", " ").strip()
        if cleaned:
            return cleaned
    fallback = (item.body or item.title).replace("\r", " ").replace("\n", " ").strip()
    return f"{fallback[:237].rstrip()}..." if len(fallback) > 240 else fallback


def _packet_source_snapshot(
    db: Session,
    thread: OpportunityThread,
    snapshot: Opportunity,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], str]:
    rows = list(
        db.execute(
            select(NormalizedItem, ItemSignal)
            .join(ClusterItem, ClusterItem.item_id == NormalizedItem.id)
            .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id)
            .where(ClusterItem.cluster_id == snapshot.cluster_id)
            .order_by(
                ItemSignal.pain_score.desc(),
                ItemSignal.task_concreteness_score.desc(),
                NormalizedItem.created_at.desc(),
            )
        ).all()
    )
    items = [item for item, _signal in rows]
    item_ids = [item.id for item in items]
    human = get_review_snapshots(db, item_ids)
    agent = get_agent_review_snapshots(db, item_ids)
    if unresolved_sensitive_risk(human, agent):
        raise _not_ready("sensitive_risk")
    readiness = calculate_evidence_readiness(items, human)
    if readiness.level not in {
        EvidenceReadinessLevel.MEDIUM,
        EvidenceReadinessLevel.STRONG,
    }:
        raise _not_ready("evidence_readiness_weak")

    run = _resolve_packet_run(db, thread, snapshot)
    scan_id = snapshot.scan_id or (run.scan_id if run is not None else None)
    observations = (
        {
            row.item_id: row
            for row in db.scalars(
                select(ScanItem).where(
                    ScanItem.scan_id == scan_id,
                    ScanItem.item_id.in_(item_ids),
                )
            ).all()
        }
        if scan_id is not None and item_ids
        else {}
    )
    evidence: list[dict[str, Any]] = []
    for item, signal in rows:
        observation = observations.get(item.id)
        review = human.get(item.id)
        evidence.append(
            {
                "id": str(item.id),
                "source": (
                    observation.observed_source
                    if observation is not None and observation.observed_source
                    else item.source
                ),
                "external_id": (
                    observation.observed_external_id
                    if observation is not None and observation.observed_external_id
                    else item.external_id
                ),
                "title": item.title,
                "excerpt": _evidence_excerpt(item, signal),
                "source_url": safe_public_source_url(
                    observation.observed_url
                    if observation is not None and observation.observed_url
                    else item.url
                ),
                "evidence_hash": item.text_hash,
                "scan_id": str(scan_id) if scan_id is not None else None,
                "run_id": str(run.id) if run is not None else None,
                "project_id": str(thread.project_id) if thread.project_id else None,
                "created_at": _utc(item.created_at).isoformat(),
                "signal_type": signal.signal_type,
                "review_label": (
                    review.review_label.value
                    if review is not None and review.review_label is not None
                    else None
                ),
            }
        )

    decision_event = db.scalar(
        select(OpportunityDecisionEvent)
        .where(
            OpportunityDecisionEvent.thread_id == thread.id,
            OpportunityDecisionEvent.event_type.in_(("decision_changed", "legacy_backfill")),
            OpportunityDecisionEvent.next_state == thread.review_state,
        )
        .order_by(
            OpportunityDecisionEvent.created_at.desc(),
            OpportunityDecisionEvent.id.desc(),
        )
        .limit(1)
    )
    decision = (
        {
            "id": str(decision_event.id),
            "event_type": decision_event.event_type,
            "actor_type": decision_event.actor_type,
            "agent_session_id": (
                str(decision_event.agent_session_id)
                if decision_event.agent_session_id is not None
                else None
            ),
            "snapshot_id": (
                str(decision_event.snapshot_id)
                if decision_event.snapshot_id is not None
                else None
            ),
            "related_thread_id": (
                str(decision_event.related_thread_id)
                if decision_event.related_thread_id is not None
                else None
            ),
            "previous_state": decision_event.previous_state,
            "next_state": decision_event.next_state,
            "created_at": _utc(decision_event.created_at).isoformat(),
        }
        if decision_event is not None
        else None
    )
    safe_snapshot = {
        "title": snapshot.title,
        "problem_statement": snapshot.problem_statement,
        "target_user": snapshot.target_user,
        "current_workaround": snapshot.current_workaround,
        "suggested_mvp": snapshot.suggested_mvp,
        "why_now": snapshot.why_now,
        "feasibility_score": snapshot.feasibility_score,
        "opportunity_score": snapshot.opportunity_score,
        "competition_notes": snapshot.competition_notes,
        "review_state": thread.review_state,
        "readiness": readiness.level.value,
        "evidence_hash": snapshot.evidence_hash,
        "content_hash": snapshot.content_hash,
        "match_method": snapshot.match_method,
        "match_confidence": snapshot.match_confidence,
        "decision": decision,
    }
    source_snapshot = {
        "thread_version": thread.version,
        "lineage_status": thread.lineage_status,
        "opportunity": safe_snapshot,
        "evidence": evidence,
        "readiness": readiness.model_dump(mode="json"),
    }
    signature = _packet_sha256(_canonical_packet_json(source_snapshot))
    return safe_snapshot, evidence, source_snapshot, signature


def _enhancement_failure_code(exc: Exception) -> str:
    if isinstance(exc, EnhancementUnavailable):
        return "unavailable"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPError):
        return "provider_error"
    return "invalid_response"


def _create_build_packet(
    db: Session,
    request: Mapping[str, Any],
    *,
    session_id: UUID,
    raw_session_secret: str,
    correlation_id: UUID,
) -> dict[str, Any]:
    payload = _CreateBuildPacket.model_validate(request)
    if payload.use_configured_ai:
        elected_owner = db.scalar(
            select(AgentAction)
            .where(
                AgentAction.tool_name == "create_build_packet",
                AgentAction.event_status == "reserved",
                AgentAction.correlation_id == correlation_id,
            )
            .order_by(AgentAction.created_at, AgentAction.id)
            .limit(1)
        )
        if elected_owner is not None and elected_owner.session_id != session_id:
            raise MCPWriteDomainError("idempotency_in_progress")
    thread = db.scalar(
        select(OpportunityThread)
        .where(OpportunityThread.id == payload.thread_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if thread is None:
        raise _not_found("opportunity_thread")
    if thread.version != payload.expected_version:
        raise _version_conflict(payload.expected_version, thread.version)
    if thread.review_state != ReviewState.BUILD_CANDIDATE.value:
        raise _not_ready("build_candidate_required")
    if thread.current_snapshot_id is None:
        raise _not_ready("current_snapshot_required")
    snapshot = db.get(Opportunity, thread.current_snapshot_id)
    if snapshot is None or snapshot.thread_id != thread.id:
        raise MCPWriteDomainError("domain_conflict")

    thread_version = thread.version
    snapshot_id = snapshot.id
    safe_snapshot, evidence, source_snapshot, signature = _packet_source_snapshot(
        db, thread, snapshot
    )
    run = _resolve_packet_run(db, thread, snapshot)
    project_id = thread.project_id if run is not None else None
    run_id = run.id if run is not None else None
    lineage_status = thread.lineage_status
    packet_id = uuid4()
    generated_at = datetime.now(UTC)
    generated = build_packet_artifacts(
        safe_snapshot,
        evidence,
        BuildPacketMetadata(
            packet_id=packet_id,
            project_id=project_id,
            run_id=run_id,
            thread_id=thread.id,
            snapshot_id=snapshot_id,
            tasksignal_version=TASKSIGNAL_VERSION,
            schema_version=BUILD_PACKET_SCHEMA_VERSION,
            template_version=BUILD_PACKET_TEMPLATE_VERSION,
        ),
        generated_at,
    )
    decision = safe_snapshot.get("decision")
    manifest = {
        **generated.manifest,
        "source_snapshot_sha256": signature,
        "lineage_status": lineage_status,
        "decision_event_id": decision.get("id") if isinstance(decision, dict) else None,
        "decision_sha256": (
            _packet_sha256(_canonical_packet_json(decision))
            if isinstance(decision, dict)
            else None
        ),
    }

    # Release the SQLite write transaction before optional provider I/O. The action
    # reservation is in its own committed transaction; eligibility is revalidated
    # under a fresh write lock before the immutable packet and success audit commit.
    db.rollback()
    enhanced_artifacts: dict[str, str] | None = None
    enhancement_status = "not_requested"
    enhancement_provider: str | None = None
    enhancement_model: str | None = None
    enhancement_template_version: str | None = None
    if payload.use_configured_ai:
        provider_hint = configured_provider()
        provider_metadata = provider_hint if provider_hint != "none" else "unconfigured"
        model_metadata = settings.llm_model.strip() or "unconfigured"
        try:
            provider, model, raw = enhance_prompt(build_enhancement_prompt(generated.artifacts))
            enhanced_artifacts = parse_enhanced_documents(raw)
            enhancement_status = "generated"
            enhancement_provider = provider
            enhancement_model = model
            manifest = manifest_with_enhancement(
                manifest,
                status="generated",
                provider=provider,
                model=model,
                enhanced_artifacts=enhanced_artifacts,
            )
        except (
            AttributeError,
            EnhancementUnavailable,
            InvalidBuildPacketEnhancement,
            TypeError,
            ValueError,
            httpx.HTTPError,
        ) as exc:
            enhancement_status = "fallback"
            enhancement_provider = provider_metadata
            enhancement_model = model_metadata
            manifest = manifest_with_enhancement(
                manifest,
                status="fallback",
                provider=provider_metadata,
                model=model_metadata,
                failure_code=_enhancement_failure_code(exc),
            )
        enhancement_template_version = ENHANCEMENT_TEMPLATE_VERSION

    verification = verify_packet_artifacts(
        generated.artifacts,
        manifest,
        enhanced_artifacts,
    )
    if not verification.valid:
        raise MCPWriteDomainError("packet_integrity_error")

    # Provider I/O runs outside the database transaction. Reauthenticate both the
    # standard write and separately selected AI capability before persistence.
    _authorize_agent_action_session(
        db,
        session_id=session_id,
        raw_session_secret=raw_session_secret,
        tool_name="create_build_packet",
        request=request,
    )
    fresh_thread = db.scalar(
        select(OpportunityThread)
        .where(OpportunityThread.id == payload.thread_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if fresh_thread is None:
        raise _not_found("opportunity_thread")
    if fresh_thread.version != thread_version:
        raise _version_conflict(thread_version, fresh_thread.version)
    if (
        fresh_thread.review_state != ReviewState.BUILD_CANDIDATE.value
        or fresh_thread.current_snapshot_id != snapshot_id
    ):
        raise MCPWriteDomainError("eligibility_conflict")
    fresh_snapshot = db.get(Opportunity, snapshot_id)
    if fresh_snapshot is None:
        raise MCPWriteDomainError("eligibility_conflict")
    _safe, _evidence, _source, fresh_signature = _packet_source_snapshot(
        db, fresh_thread, fresh_snapshot
    )
    if fresh_signature != signature:
        raise MCPWriteDomainError("eligibility_conflict")

    generation_mode = "configured_ai" if payload.use_configured_ai else "deterministic"
    manifest_content = _canonical_packet_json(manifest)
    packet = BuildPacket(
        id=packet_id,
        project_id=project_id,
        run_id=run_id,
        thread_id=fresh_thread.id,
        snapshot_id=fresh_snapshot.id,
        lineage_status=lineage_status,
        generation_mode=generation_mode,
        schema_version=BUILD_PACKET_SCHEMA_VERSION,
        tasksignal_version=TASKSIGNAL_VERSION,
        template_version=BUILD_PACKET_TEMPLATE_VERSION,
        source_snapshot_json=source_snapshot,
        artifacts_json=generated.artifacts,
        manifest_json=manifest,
        manifest_sha256=_packet_sha256(manifest_content),
        enhancement_status=enhancement_status,
        enhanced_artifacts_json=enhanced_artifacts,
        enhancement_provider=enhancement_provider,
        enhancement_model=enhancement_model,
        enhancement_template_version=enhancement_template_version,
        generated_at=generated_at,
    )
    db.add(packet)
    db.flush()
    return {
        "id": packet.id,
        "packet_id": packet.id,
        "thread_id": packet.thread_id,
        "snapshot_id": packet.snapshot_id,
        "version": fresh_thread.version,
        "generation_mode": generation_mode,
        "enhancement_status": enhancement_status,
        "artifact_count": 10 + len(enhanced_artifacts or {}),
        "status": "created",
    }


def _mutation_for(
    operation: str,
    request: Mapping[str, Any],
    session_id: UUID,
    raw_session_secret: str,
    correlation_id: UUID,
) -> Callable[[Session], dict[str, Any]]:
    if operation == "create_project":
        return lambda db: _create_project(db, request)
    if operation == "update_project":
        return lambda db: _update_project(db, request)
    if operation == "run_project":
        return lambda db: _run_project(
            db,
            request,
            session_id=session_id,
            raw_session_secret=raw_session_secret,
            scan_id=correlation_id,
        )
    if operation == "set_opportunity_decision":
        return lambda db: _set_opportunity_decision(
            db, request, session_id=session_id
        )
    if operation == "append_evidence_label":
        return lambda db: _append_evidence_label(db, request, session_id=session_id)
    if operation == "create_build_packet":
        return lambda db: _create_build_packet(
            db,
            request,
            session_id=session_id,
            raw_session_secret=raw_session_secret,
            correlation_id=correlation_id,
        )
    raise MCPWriteDomainError("unsupported_operation", denied=True)


def _claim_for_reserved(event: AgentAction) -> ActionClaim:
    return ActionClaim(
        operation_id=event.operation_id,
        correlation_id=event.correlation_id,
        event=event,
        outcome="reserved",
    )


def _terminal_execution(
    execution: AgentActionExecution,
    terminal: AgentAction,
) -> AgentActionExecution:
    result = (
        summarize_result(terminal.tool_name, terminal.result_summary_json)
        if terminal.result_summary_json is not None
        else None
    )
    return AgentActionExecution(
        outcome="replay",
        operation_id=execution.operation_id,
        correlation_id=execution.correlation_id,
        result=result,
        error_code=terminal.error_code or IDEMPOTENCY_REPLAY,
    )


def _recover_in_progress_run(
    session_factory: SessionFactory,
    *,
    execution: AgentActionExecution,
    session_id: UUID,
    raw_session_secret: str,
    request: Mapping[str, Any],
) -> AgentActionExecution | None:
    """Resume pre-scan crashes or terminalize a scan committed before its audit."""

    with session_factory() as db:
        _authorize_agent_action_session(
            db,
            session_id=session_id,
            raw_session_secret=raw_session_secret,
            tool_name="run_project",
            request=request,
        )
        reserved = db.scalar(
            select(AgentAction)
            .where(
                AgentAction.operation_id == execution.operation_id,
                AgentAction.event_status == "reserved",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if reserved is None:
            db.rollback()
            return None
        terminal = _core_terminal_event(db, reserved.operation_id)
        if terminal is not None:
            db.rollback()
            return _terminal_execution(execution, terminal)

        payload = _RunProject.model_validate(request)
        scan = db.scalar(
            select(ScanJob)
            .where(ScanJob.id == reserved.correlation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if scan is None:
            result = _run_project(
                db,
                request,
                session_id=session_id,
                raw_session_secret=raw_session_secret,
                scan_id=reserved.correlation_id,
            )
        elif scan.status in {"completed", "failed"}:
            result = _run_result_for_scan(
                db,
                project_id=payload.project_id,
                scan=scan,
            )
        else:
            prior_reservations = list(
                db.scalars(
                    select(AgentAction).where(
                        AgentAction.tool_name == "run_project",
                        AgentAction.event_status == "reserved",
                        AgentAction.correlation_id == scan.id,
                        AgentAction.operation_id != reserved.operation_id,
                    )
                )
            )
            incomplete_prior = [
                event
                for event in prior_reservations
                if _core_terminal_event(db, event.operation_id) is None
            ]
            if not incomplete_prior:
                db.rollback()
                return None
            for event in incomplete_prior:
                owner = db.get(AgentSession, event.session_id)
                if owner is None:
                    continue
                expire_session_if_needed(owner)
                if owner.status in {"pending", "approved"}:
                    db.rollback()
                    return None

            finished_at = datetime.now(UTC)
            scan.status = "failed"
            scan.finished_at = finished_at
            scan.error_message = (
                "The originating MCP process ended before this scan completed."
            )
            scan.outcome_message = (
                "The incomplete scan was closed without persisting fetched evidence."
            )
            run = db.scalar(
                select(ResearchProjectRun).where(
                    ResearchProjectRun.project_id == payload.project_id,
                    ResearchProjectRun.scan_id == scan.id,
                )
            )
            if run is not None:
                mark_latest_project_run(
                    db,
                    project_id=run.project_id,
                    run_sequence=run.sequence,
                    scan_id=scan.id,
                    finished_at=finished_at,
                )
            db.flush()
            result = _run_result_for_scan(
                db,
                project_id=payload.project_id,
                scan=scan,
            )

        reserved = db.scalar(
            select(AgentAction)
            .where(
                AgentAction.operation_id == execution.operation_id,
                AgentAction.event_status == "reserved",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if reserved is None:
            db.rollback()
            return None
        terminal = _core_terminal_event(db, reserved.operation_id)
        if terminal is None:
            try:
                complete_agent_action(db, claim=_claim_for_reserved(reserved), result=result)
                db.commit()
            except InvalidActionTransition:
                db.rollback()
                terminal = _core_terminal_event(db, reserved.operation_id)
                if terminal is None:
                    raise
        else:
            db.rollback()
        if terminal is not None:
            return _terminal_execution(execution, terminal)
    return AgentActionExecution(
        outcome="replay",
        operation_id=execution.operation_id,
        correlation_id=execution.correlation_id,
        result=result,
        error_code=IDEMPOTENCY_REPLAY,
    )


def _reconcile_reserved_run_actions(
    session_factory: SessionFactory,
    *,
    scan_id: UUID,
    result: Mapping[str, Any],
) -> None:
    """Close older process reservations linked to an already terminal scan."""

    with session_factory() as db:
        acquire_database_scan_write_lock_with_retry(db)
        reservations = list(
            db.scalars(
                select(AgentAction)
                .where(
                    AgentAction.tool_name == "run_project",
                    AgentAction.event_status == "reserved",
                    AgentAction.correlation_id == scan_id,
                )
                .order_by(AgentAction.created_at, AgentAction.id)
                .with_for_update()
            )
        )
        for reserved in reservations:
            if _core_terminal_event(db, reserved.operation_id) is not None:
                continue
            try:
                complete_agent_action(db, claim=_claim_for_reserved(reserved), result=result)
            except InvalidActionTransition:
                continue
        db.commit()


def _recover_in_progress_ai_packet(
    session_factory: SessionFactory,
    *,
    execution: AgentActionExecution,
    session_id: UUID,
    raw_session_secret: str,
    request: Mapping[str, Any],
) -> AgentActionExecution | None:
    """Replay a prior result or stop ambiguous paid I/O after process loss."""

    with session_factory() as db:
        _authorize_agent_action_session(
            db,
            session_id=session_id,
            raw_session_secret=raw_session_secret,
            tool_name="create_build_packet",
            request=request,
        )
        current = db.scalar(
            select(AgentAction)
            .where(
                AgentAction.operation_id == execution.operation_id,
                AgentAction.event_status == "reserved",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if current is None:
            db.rollback()
            return None
        current_terminal = _core_terminal_event(db, current.operation_id)
        if current_terminal is not None:
            db.rollback()
            return _terminal_execution(execution, current_terminal)

        prior = list(
            db.scalars(
                select(AgentAction)
                .where(
                    AgentAction.tool_name == "create_build_packet",
                    AgentAction.event_status == "reserved",
                    AgentAction.correlation_id == execution.correlation_id,
                    AgentAction.operation_id != current.operation_id,
                )
                .order_by(AgentAction.created_at, AgentAction.id)
                .with_for_update()
            )
        )
        if not prior:
            db.rollback()
            return None

        terminal_pairs = [
            (event, terminal)
            for event in prior
            if (terminal := _core_terminal_event(db, event.operation_id)) is not None
        ]
        succeeded = next(
            (
                (event, terminal)
                for event, terminal in terminal_pairs
                if terminal.event_status == "succeeded"
            ),
            None,
        )
        if succeeded is not None:
            _event, terminal = succeeded
            result = summarize_result(terminal.tool_name, terminal.result_summary_json or {})
            complete_agent_action(db, claim=_claim_for_reserved(current), result=result)
            db.commit()
            return AgentActionExecution(
                outcome="replay",
                operation_id=current.operation_id,
                correlation_id=current.correlation_id,
                result=result,
                error_code=IDEMPOTENCY_REPLAY,
            )

        if terminal_pairs:
            _event, terminal = terminal_pairs[0]
            error_code = terminal.error_code or "replayed_failure"
            fail_agent_action(
                db,
                claim=_claim_for_reserved(current),
                error_code=error_code,
                result={},
            )
            db.commit()
            return AgentActionExecution(
                outcome="replay",
                operation_id=current.operation_id,
                correlation_id=current.correlation_id,
                result={},
                error_code=error_code,
            )

        for event in prior:
            owner = db.get(AgentSession, event.session_id)
            if owner is None:
                continue
            expire_session_if_needed(owner)
            if owner.status in {"pending", "approved"}:
                db.rollback()
                return None

        error_code = "external_effect_indeterminate"
        for event in prior:
            try:
                fail_agent_action(
                    db,
                    claim=_claim_for_reserved(event),
                    error_code=error_code,
                    result={},
                )
            except InvalidActionTransition:
                continue
        fail_agent_action(
            db,
            claim=_claim_for_reserved(current),
            error_code=error_code,
            result={},
        )
        db.commit()
        return AgentActionExecution(
            outcome="replay",
            operation_id=current.operation_id,
            correlation_id=current.correlation_id,
            result={},
            error_code=error_code,
        )


def execute_mcp_write(
    session_factory: SessionFactory,
    *,
    session_id: UUID,
    raw_session_secret: str,
    operation: str,
    idempotency_key: str,
    expected_version: int,
    arguments: Mapping[str, Any],
) -> dict[str, Any]:
    """Dispatch one of the six non-destructive v1 MCP writes.

    Transport adapters pass the raw process-held secret only to this boundary. The
    request is hashed in full but persisted only through the action service's strict
    redacted summaries. Supported operations always enter the authorized durable
    executor; validation is deliberately inside the mutation so denials are audited.
    """

    if operation not in MCP_WRITE_OPERATIONS:
        return {
            "ok": False,
            "outcome": "error",
            "operation_id": None,
            "correlation_id": None,
            "result": None,
            "error": {"code": "unsupported_operation"},
        }
    try:
        normalized_session_id = UUID(str(session_id))
    except (TypeError, ValueError, AttributeError):
        return {
            "ok": False,
            "outcome": "error",
            "operation_id": None,
            "correlation_id": None,
            "result": None,
            "error": {"code": "invalid_request"},
        }
    if not isinstance(arguments, Mapping) or not all(
        isinstance(key, str) for key in arguments
    ):
        request: dict[str, Any] = {
            "expected_version": expected_version,
            "_invalid_arguments": True,
        }
    else:
        request = dict(arguments)
        supplied_expected = request.pop("expected_version", expected_version)
        request["expected_version"] = expected_version
        if supplied_expected != expected_version:
            request["_expected_version_mismatch"] = True
    if operation == "create_build_packet":
        use_configured_ai = request.get("use_configured_ai", False)
        request.setdefault(
            "generation_mode",
            "configured_ai" if use_configured_ai is True else "deterministic",
        )
    if operation == "run_project":
        correlation_id = _run_scan_id(idempotency_key, request)
    elif operation == "create_build_packet" and request.get("use_configured_ai") is True:
        correlation_id = _configured_ai_packet_correlation_id(idempotency_key, request)
    else:
        correlation_id = uuid4()

    try:
        execution = execute_audited_agent_action(
            session_factory,
            session_id=normalized_session_id,
            raw_session_secret=raw_session_secret,
            tool_name=operation,
            idempotency_key=idempotency_key,
            request=request,
            correlation_id=correlation_id,
            mutation=_mutation_for(
                operation,
                request,
                normalized_session_id,
                raw_session_secret,
                correlation_id,
            ),
            failure_mapper=_failure_mapper,
        )
    except Exception as exc:
        return {
            "ok": False,
            "outcome": "error",
            "operation_id": None,
            "correlation_id": None,
            "result": None,
            "error": _public_error(exc),
        }
    if operation == "run_project" and execution.outcome == "in_progress":
        try:
            recovered = _recover_in_progress_run(
                session_factory,
                execution=execution,
                session_id=normalized_session_id,
                raw_session_secret=raw_session_secret,
                request=request,
            )
        except Exception as exc:
            return {
                "ok": False,
                "outcome": "error",
                "operation_id": str(execution.operation_id),
                "correlation_id": str(execution.correlation_id),
                "result": None,
                "error": _public_error(exc),
            }
        if recovered is not None:
            execution = recovered
    if (
        operation == "create_build_packet"
        and request.get("use_configured_ai") is True
        and execution.outcome == "in_progress"
    ):
        try:
            recovered_packet = _recover_in_progress_ai_packet(
                session_factory,
                execution=execution,
                session_id=normalized_session_id,
                raw_session_secret=raw_session_secret,
                request=request,
            )
        except Exception as exc:
            return {
                "ok": False,
                "outcome": "error",
                "operation_id": str(execution.operation_id),
                "correlation_id": str(execution.correlation_id),
                "result": None,
                "error": _public_error(exc),
            }
        if recovered_packet is not None:
            execution = recovered_packet
    if (
        operation == "run_project"
        and execution.outcome in {"succeeded", "replay"}
        and isinstance(execution.result, Mapping)
        and execution.result.get("status") in {"completed", "failed"}
    ):
        try:
            scan_id = UUID(str(execution.result["id"]))
            _reconcile_reserved_run_actions(
                session_factory,
                scan_id=scan_id,
                result=execution.result,
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            pass
    return _result_envelope(execution)
