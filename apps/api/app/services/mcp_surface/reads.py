"""Redacted, JSON-serializable reads shared by the stdio MCP surface.

This module deliberately has no dependency on the MCP SDK, FastAPI routes, or
transport state. Public evidence is always represented as a bounded excerpt;
local review notes, source payloads, author hashes, and connector configuration
never enter these return values.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, unquote, urlsplit
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    BuildPacket,
    ClusterItem,
    ItemSignal,
    NormalizedItem,
    Opportunity,
    OpportunityDecisionEvent,
    OpportunityThread,
    ResearchProject,
    ResearchProjectRun,
    ScanItem,
    ScanJob,
)
from app.schemas.api import (
    BuildPacketArtifactOut,
    BuildPacketOut,
    BuildPacketVerificationOut,
    ResearchProjectOut,
    ResearchRunOut,
    RunDeltaOut,
    SemanticSearchRequest,
)
from app.services.build_packets import (
    MANIFEST_FILENAME,
    redact_public_text,
    safe_public_source_url,
    verify_packet_artifacts,
)
from app.services.evidence_review.service import (
    calculate_evidence_readiness,
    evaluation_summary,
    get_review_snapshots,
)
from app.services.evidence_review.types import EvidenceReviewSnapshot
from app.services.research_memory.service import (
    IncompleteRunError,
    calculate_run_delta,
    get_project_run,
)
from app.services.research_memory.service import (
    list_project_runs as list_stored_project_runs,
)
from app.services.search.service import SemanticEmbedder, semantic_search

JSON_MIME_TYPE = "application/json"
MARKDOWN_MIME_TYPE = "text/markdown; charset=utf-8"
_MAX_ARTIFACT_NAME_LENGTH = 256


class McpReadError(ValueError):
    """A safe, structured domain error for transport adapters."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _identifier(value: UUID | str, field: str, *, resource: bool = False) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError) as exc:
        code = "invalid_resource_uri" if resource else "invalid_argument"
        raise McpReadError(code, f"{field} is an invalid UUID.") from exc


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _canonical_json(value: object) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        + "\n"
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_text(value: str | None, limit: int) -> str:
    normalized = " ".join(redact_public_text(value or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _safe_optional_text(value: str | None, limit: int) -> str | None:
    return None if value is None else _safe_text(value, limit)


def _safe_project_out(project: ResearchProject) -> ResearchProjectOut:
    output = ResearchProjectOut.model_validate(project)
    return output.model_copy(
        update={
            "name": _safe_text(output.name, 120),
            "description": _safe_optional_text(output.description, 500),
            "source_type": _safe_text(output.source_type, 60),
            "query": _safe_text(output.query, 300),
            "cadence": _safe_text(output.cadence, 60),
            "labels": [_safe_text(label, 100) for label in output.labels],
            "last_scan_status": _safe_optional_text(output.last_scan_status, 60),
        }
    )


def _safe_source_origin(value: str | None) -> str | None:
    if value is None:
        return None
    if value.casefold().startswith(("http://", "https://")):
        return safe_public_source_url(value)
    return _safe_text(value, 300)


def _research_run_out(run: ResearchProjectRun) -> ResearchRunOut:
    scan = run.scan
    return ResearchRunOut(
        id=run.id,
        project_id=run.project_id,
        scan_id=run.scan_id,
        sequence=run.sequence,
        source_type=_safe_optional_text(run.source_type, 60),
        source_origin=_safe_source_origin(run.source_origin),
        query=_safe_optional_text(run.query, 300),
        requested_limit=run.requested_limit,
        lineage_status="complete" if run.lineage_complete else "incomplete",
        scan_status=scan.status,
        started_at=scan.started_at,
        finished_at=scan.finished_at,
        items_found=scan.items_found,
        items_saved=scan.items_saved,
        signals_detected=scan.signals_detected,
        clusters_created=scan.clusters_created,
        opportunities_created=scan.opportunities_created,
        created_at=run.created_at,
    )


def _untracked_run_out(project: ResearchProject, scan: ScanJob) -> ResearchRunOut:
    return ResearchRunOut(
        id=scan.id,
        project_id=project.id,
        scan_id=scan.id,
        sequence=None,
        source_type=_safe_optional_text(scan.source_type or project.source_type, 60),
        source_origin=None,
        query=_safe_optional_text(scan.query, 300),
        requested_limit=None,
        lineage_status="untracked",
        scan_status=scan.status,
        started_at=scan.started_at,
        finished_at=scan.finished_at,
        items_found=scan.items_found,
        items_saved=scan.items_saved,
        signals_detected=scan.signals_detected,
        clusters_created=scan.clusters_created,
        opportunities_created=scan.opportunities_created,
        created_at=scan.started_at,
    )


def list_projects(db: Session) -> list[dict[str, Any]]:
    """List saved research projects without connector configuration."""

    projects = db.scalars(
        select(ResearchProject).order_by(
            ResearchProject.updated_at.desc(),
            ResearchProject.id.desc(),
        )
    ).all()
    return [_safe_project_out(project).model_dump(mode="json") for project in projects]


def list_project_runs(
    db: Session,
    project_id: UUID | str,
) -> list[dict[str, Any]]:
    """List immutable tracked run snapshots and an explicitly untracked legacy run."""

    project_uuid = _identifier(project_id, "project_id")
    project = db.get(ResearchProject, project_uuid)
    if project is None:
        raise McpReadError("not_found", "Research project not found.")
    runs = list_stored_project_runs(db, project_uuid)
    output = [_research_run_out(run) for run in runs]
    tracked_scan_ids = {run.scan_id for run in runs}
    if project.last_scan_id is not None and project.last_scan_id not in tracked_scan_ids:
        legacy_scan = db.get(ScanJob, project.last_scan_id)
        if legacy_scan is not None:
            output.append(_untracked_run_out(project, legacy_scan))
    return [row.model_dump(mode="json") for row in output]


def compare_project_runs(
    db: Session,
    project_id: UUID | str,
    run_id: UUID | str,
) -> dict[str, Any]:
    """Return precise evidence/signal/thread deltas for one complete run."""

    project_uuid = _identifier(project_id, "project_id")
    run_uuid = _identifier(run_id, "run_id")
    project = db.get(ResearchProject, project_uuid)
    if project is None:
        raise McpReadError("not_found", "Research project not found.")
    run = get_project_run(db, project_uuid, run_uuid)
    if run is None:
        if project.last_scan_id == run_uuid:
            raise McpReadError(
                "run_not_comparable",
                "Legacy run lineage is untracked and cannot be compared safely.",
            )
        raise McpReadError("not_found", "Research run not found.")
    try:
        delta = calculate_run_delta(db, run)
    except IncompleteRunError as exc:
        raise McpReadError("run_not_comparable", str(exc)) from exc
    return RunDeltaOut(
        project_id=delta.project_id,
        run_id=delta.run_id,
        scan_id=delta.scan_id,
        sequence=delta.sequence,
        previous_run_id=delta.previous_run_id,
        evidence_changes=delta.evidence_changes,
        signal_changes=delta.signal_changes,
        generated_snapshots=delta.generated_snapshots,
        opportunity_changes=delta.opportunity_changes,
        warnings=[],
    ).model_dump(mode="json")


def search_opportunities(
    db: Session,
    *,
    query: str,
    limit: int = 10,
    project_id: UUID | str | None = None,
    source: str | None = None,
    signal_type: str | None = None,
    review_state: str | None = None,
    embedder: SemanticEmbedder | None = None,
) -> dict[str, Any]:
    """Search redacted evidence excerpts and related opportunity threads."""

    if limit > 20:
        raise McpReadError("invalid_argument", "Search limit must be at most 20.")
    project_uuid = _identifier(project_id, "project_id") if project_id is not None else None
    if project_uuid is not None and db.get(ResearchProject, project_uuid) is None:
        raise McpReadError("not_found", "Research project not found.")
    try:
        request = SemanticSearchRequest(
            query=query,
            limit=limit,
            project_id=project_uuid,
            source=source,
            signal_type=signal_type,
            review_state=review_state,
        )
    except ValidationError as exc:
        raise McpReadError("invalid_argument", "Search request is invalid.") from exc
    return semantic_search(db, request, embedder=embedder).model_dump(mode="json")


def _safe_observation(
    db: Session,
    *,
    item: NormalizedItem,
    snapshot: Opportunity,
) -> tuple[str, str]:
    observation = None
    if snapshot.scan_id is not None:
        observation = db.scalar(
            select(ScanItem).where(
                ScanItem.scan_id == snapshot.scan_id,
                ScanItem.item_id == item.id,
            )
        )
    source = (
        observation.observed_source
        if observation is not None and observation.observed_source
        else item.source
    )
    source_url = (
        observation.observed_url
        if observation is not None and observation.observed_url
        else item.url
    )
    return source, safe_public_source_url(source_url)


def _snapshot_evidence(
    db: Session,
    snapshot: Opportunity,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = list(
        db.execute(
            select(NormalizedItem, ItemSignal)
            .join(ClusterItem, ClusterItem.item_id == NormalizedItem.id)
            .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id, isouter=True)
            .where(ClusterItem.cluster_id == snapshot.cluster_id)
            .order_by(NormalizedItem.id)
        ).all()
    )
    items = [item for item, _signal in rows]
    reviews = get_review_snapshots(db, [item.id for item in items])
    evidence: list[dict[str, Any]] = []
    for item, signal in rows:
        review = reviews.get(item.id, EvidenceReviewSnapshot())
        spans = signal.evidence_spans_json if signal is not None else []
        excerpt = next(
            (span for span in spans if isinstance(span, str) and span.strip()),
            item.body or item.title,
        )
        source, source_url = _safe_observation(db, item=item, snapshot=snapshot)
        evidence.append(
            {
                "id": str(item.id),
                "source": source,
                "title": _safe_text(item.title, 180),
                "excerpt": _safe_text(excerpt, 240),
                "source_url": source_url,
                "signal_type": signal.signal_type if signal is not None else None,
                "review_label": (
                    review.review_label.value if review.review_label is not None else None
                ),
                "untrusted_evidence": True,
                "provenance": {
                    "evidence_hash": item.text_hash,
                    "scan_id": str(snapshot.scan_id) if snapshot.scan_id else None,
                    "run_id": str(snapshot.run_id) if snapshot.run_id else None,
                },
            }
        )
    readiness = calculate_evidence_readiness(items, reviews).model_dump(mode="json")
    return evidence, readiness


def _snapshot_out(db: Session, snapshot: Opportunity) -> dict[str, Any]:
    evidence, readiness = _snapshot_evidence(db, snapshot)
    detached = db.scalar(
        select(OpportunityDecisionEvent.id)
        .where(
            OpportunityDecisionEvent.event_type == "snapshot_detached",
            OpportunityDecisionEvent.snapshot_id == snapshot.id,
        )
        .limit(1)
    )
    return {
        "id": str(snapshot.id),
        "thread_id": str(snapshot.thread_id),
        "run_id": str(snapshot.run_id) if snapshot.run_id else None,
        "scan_id": str(snapshot.scan_id) if snapshot.scan_id else None,
        "evidence_hash": snapshot.evidence_hash,
        "content_hash": snapshot.content_hash,
        "match_method": snapshot.match_method,
        "match_confidence": snapshot.match_confidence,
        "match_margin": snapshot.match_margin,
        "centroid_similarity": snapshot.centroid_similarity,
        "evidence_jaccard": snapshot.evidence_jaccard,
        "title_jaccard": snapshot.title_jaccard,
        "detached": detached is not None,
        "title": _safe_text(snapshot.title, 240),
        "problem_statement": _safe_text(snapshot.problem_statement, 1000),
        "target_user": _safe_text(snapshot.target_user, 500),
        "current_workaround": _safe_text(snapshot.current_workaround, 1000),
        "suggested_mvp": _safe_text(snapshot.suggested_mvp, 1000),
        "why_now": _safe_text(snapshot.why_now, 1000),
        "feasibility_score": snapshot.feasibility_score,
        "opportunity_score": snapshot.opportunity_score,
        "review_state": snapshot.review_state,
        "created_at": _as_utc(snapshot.created_at).isoformat(),
        "updated_at": _as_utc(snapshot.updated_at).isoformat(),
        "evidence_items": evidence,
        "evidence_readiness": readiness,
        "untrusted_evidence": True,
    }


def get_opportunity_thread(
    db: Session,
    thread_id: UUID | str,
) -> dict[str, Any]:
    """Return a thread and its snapshots without local decision/evidence notes."""

    thread_uuid = _identifier(thread_id, "thread_id")
    thread = db.get(OpportunityThread, thread_uuid)
    if thread is None:
        raise McpReadError("not_found", "Opportunity thread not found.")
    snapshots = list(
        db.scalars(
            select(Opportunity)
            .where(Opportunity.thread_id == thread_uuid)
            .order_by(Opportunity.created_at.desc(), Opportunity.id.desc())
        ).all()
    )
    snapshot_values = [_snapshot_out(db, snapshot) for snapshot in snapshots]
    current = next(
        (
            snapshot
            for snapshot in snapshot_values
            if snapshot["id"] == str(thread.current_snapshot_id)
        ),
        None,
    )
    events = db.scalars(
        select(OpportunityDecisionEvent)
        .where(OpportunityDecisionEvent.thread_id == thread_uuid)
        .order_by(
            OpportunityDecisionEvent.created_at.asc(),
            OpportunityDecisionEvent.id.asc(),
        )
    ).all()
    return {
        "id": str(thread.id),
        "project_id": str(thread.project_id) if thread.project_id else None,
        "lineage_status": thread.lineage_status,
        "review_state": thread.review_state,
        "decision_updated_at": (
            _as_utc(thread.decision_updated_at).isoformat() if thread.decision_updated_at else None
        ),
        "version": thread.version,
        "snapshot_count": len(snapshot_values),
        "current_snapshot": current,
        "snapshots": snapshot_values,
        "decision_history": [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "actor_type": event.actor_type,
                "agent_session_id": (
                    str(event.agent_session_id) if event.agent_session_id else None
                ),
                "snapshot_id": str(event.snapshot_id) if event.snapshot_id else None,
                "related_thread_id": (
                    str(event.related_thread_id) if event.related_thread_id else None
                ),
                "previous_state": event.previous_state,
                "next_state": event.next_state,
                "created_at": _as_utc(event.created_at).isoformat(),
            }
            for event in events
        ],
        "created_at": _as_utc(thread.created_at).isoformat(),
        "updated_at": _as_utc(thread.updated_at).isoformat(),
    }


def get_evaluation(db: Session) -> dict[str, Any]:
    """Return aggregate, human-confirmed evaluation metrics."""

    return evaluation_summary(db).model_dump(mode="json")


def _packet_files(packet: BuildPacket) -> dict[str, str]:
    if not isinstance(packet.artifacts_json, dict):
        raise McpReadError("stored_data_invalid", "Stored build packet is invalid.")
    if packet.enhanced_artifacts_json is not None and not isinstance(
        packet.enhanced_artifacts_json,
        dict,
    ):
        raise McpReadError("stored_data_invalid", "Stored build packet is invalid.")
    if not isinstance(packet.manifest_json, dict):
        raise McpReadError("stored_data_invalid", "Stored build packet is invalid.")
    files: dict[str, str] = {
        **packet.artifacts_json,
        **(packet.enhanced_artifacts_json or {}),
        MANIFEST_FILENAME: _canonical_json(packet.manifest_json),
    }
    if not all(
        isinstance(path, str) and isinstance(content, str) for path, content in files.items()
    ):
        raise McpReadError("stored_data_invalid", "Stored build packet is invalid.")
    return files


def _packet_out(packet: BuildPacket) -> BuildPacketOut:
    files = _packet_files(packet)
    return BuildPacketOut(
        id=packet.id,
        project_id=packet.project_id,
        run_id=packet.run_id,
        thread_id=packet.thread_id,
        snapshot_id=packet.snapshot_id,
        lineage_status=packet.lineage_status,
        generation_mode=packet.generation_mode,
        schema_version=packet.schema_version,
        tasksignal_version=packet.tasksignal_version,
        template_version=packet.template_version,
        generated_at=packet.generated_at,
        enhancement_status=packet.enhancement_status,
        enhancement_provider=packet.enhancement_provider,
        enhancement_model=packet.enhancement_model,
        enhancement_template_version=packet.enhancement_template_version,
        artifacts=[
            BuildPacketArtifactOut(
                path=path,
                content=content,
                byte_count=len(content.encode("utf-8")),
                sha256=_sha256_text(content),
            )
            for path, content in sorted(files.items())
        ],
        manifest=packet.manifest_json,
        manifest_sha256=packet.manifest_sha256,
        created_at=packet.created_at,
    )


def get_build_packet(
    db: Session,
    packet_id: UUID | str,
) -> dict[str, Any]:
    """Return immutable packet artifacts, omitting its private source snapshot."""

    packet_uuid = _identifier(packet_id, "packet_id")
    packet = db.get(BuildPacket, packet_uuid)
    if packet is None:
        raise McpReadError("not_found", "Build packet not found.")
    return _packet_out(packet).model_dump(mode="json")


def _verification_out(packet: BuildPacket) -> BuildPacketVerificationOut:
    originals = dict(packet.artifacts_json) if isinstance(packet.artifacts_json, dict) else {}
    enhanced = (
        dict(packet.enhanced_artifacts_json)
        if isinstance(packet.enhanced_artifacts_json, dict)
        else {}
    )
    manifest = packet.manifest_json if isinstance(packet.manifest_json, dict) else {}
    verification = verify_packet_artifacts(originals, manifest, enhanced)
    errors = list(verification.errors)
    if not isinstance(packet.manifest_json, dict):
        errors.append("MANIFEST.json must contain an object")
    manifest_content = _canonical_json(packet.manifest_json)
    if _sha256_text(manifest_content) != packet.manifest_sha256:
        errors.append("MANIFEST.json sha256 mismatch")
    source_snapshot = (
        packet.source_snapshot_json if isinstance(packet.source_snapshot_json, dict) else {}
    )
    if not isinstance(packet.source_snapshot_json, dict):
        errors.append("source snapshot must contain an object")
    if manifest.get("source_snapshot_sha256") != _sha256_text(
        _canonical_json(packet.source_snapshot_json)
    ):
        errors.append("source snapshot sha256 mismatch")
    opportunity_snapshot = source_snapshot.get("opportunity")
    decision = (
        opportunity_snapshot.get("decision") if isinstance(opportunity_snapshot, dict) else None
    )
    expected_decision_id = decision.get("id") if isinstance(decision, dict) else None
    expected_decision_hash = (
        _sha256_text(_canonical_json(decision)) if isinstance(decision, dict) else None
    )
    if manifest.get("decision_event_id") != expected_decision_id:
        errors.append("manifest metadata mismatch for decision_event_id")
    if manifest.get("decision_sha256") != expected_decision_hash:
        errors.append("manifest metadata mismatch for decision_sha256")
    expected_metadata = {
        "packet_id": str(packet.id),
        "project_id": str(packet.project_id) if packet.project_id else None,
        "run_id": str(packet.run_id) if packet.run_id else None,
        "thread_id": str(packet.thread_id),
        "snapshot_id": str(packet.snapshot_id),
        "lineage_status": packet.lineage_status,
        "schema_version": packet.schema_version,
        "tasksignal_version": packet.tasksignal_version,
        "template_version": packet.template_version,
        "generation_mode": packet.generation_mode,
        "generated_at": _as_utc(packet.generated_at).isoformat().replace("+00:00", "Z"),
    }
    for key, expected in expected_metadata.items():
        if manifest.get(key) != expected:
            errors.append(f"manifest metadata mismatch for {key}")
    enhancement = manifest.get("enhancement")
    if not isinstance(enhancement, dict) or enhancement.get("status") != packet.enhancement_status:
        errors.append("manifest metadata mismatch for enhancement_status")
    elif packet.enhancement_status != "not_requested":
        if enhancement.get("provider") != packet.enhancement_provider:
            errors.append("manifest metadata mismatch for enhancement_provider")
        if enhancement.get("model") != packet.enhancement_model:
            errors.append("manifest metadata mismatch for enhancement_model")
        if enhancement.get("template_version") != packet.enhancement_template_version:
            errors.append("manifest metadata mismatch for enhancement_template_version")

    missing: list[str] = []
    unexpected: list[str] = []
    mismatched: list[str] = []
    for error in errors:
        if error.startswith(("missing packet file(s): ", "missing enhanced packet file(s): ")):
            missing.extend(error.split(": ", 1)[1].split(", "))
        elif error.startswith(
            (
                "manifest is missing artifact(s): ",
                "manifest is missing enhanced artifact(s): ",
            )
        ):
            missing.extend(error.split(": ", 1)[1].split(", "))
        elif error.startswith(
            ("manifested file is missing: ", "manifested enhanced file is missing: ")
        ):
            missing.append(error.split(": ", 1)[1])
        elif error.startswith(
            ("unexpected packet file(s): ", "unexpected enhanced packet file(s): ")
        ):
            unexpected.extend(error.split(": ", 1)[1].split(", "))
        elif error.startswith(("byte count mismatch for ", "sha256 mismatch for ")):
            mismatched.append(error.rsplit(" for ", 1)[1])
        elif error == "MANIFEST.json sha256 mismatch":
            mismatched.append(MANIFEST_FILENAME)
    return BuildPacketVerificationOut(
        packet_id=packet.id,
        valid=not errors,
        errors=list(dict.fromkeys(errors)),
        missing_files=sorted(set(missing)),
        unexpected_files=sorted(set(unexpected)),
        mismatched_files=sorted(set(mismatched)),
    )


def verify_build_packet(
    db: Session,
    packet_id: UUID | str,
) -> dict[str, Any]:
    """Verify stored packet content, hashes, and immutable lineage metadata."""

    packet_uuid = _identifier(packet_id, "packet_id")
    packet = db.get(BuildPacket, packet_uuid)
    if packet is None:
        raise McpReadError("not_found", "Build packet not found.")
    return _verification_out(packet).model_dump(mode="json")


def list_resource_templates() -> list[dict[str, str]]:
    """Describe the three URI shapes implemented by :func:`resolve_resource`."""

    return [
        {
            "uri_template": "tasksignal://projects/{project_id}/runs/{run_id}/delta",
            "name": "Project run delta",
            "description": "Precise evidence, signal, and opportunity changes for a run.",
            "mime_type": JSON_MIME_TYPE,
        },
        {
            "uri_template": "tasksignal://opportunity-threads/{thread_id}",
            "name": "Opportunity thread",
            "description": "A redacted opportunity thread with immutable snapshots.",
            "mime_type": JSON_MIME_TYPE,
        },
        {
            "uri_template": ("tasksignal://build-packets/{packet_id}/artifacts/{artifact_name}"),
            "name": "Build packet artifact",
            "description": "One immutable deterministic or enhanced packet artifact.",
            "mime_type": "text/plain; charset=utf-8",
        },
    ]


def _artifact_mime_type(name: str) -> str:
    if name.endswith(".json"):
        return JSON_MIME_TYPE
    if name.endswith(".md"):
        return MARKDOWN_MIME_TYPE
    return "text/plain; charset=utf-8"


def list_resources(db: Session) -> list[dict[str, str]]:
    """List concrete, currently readable TaskSignal resources deterministically."""

    resources: list[dict[str, str]] = []
    comparable_runs = db.execute(
        select(ResearchProjectRun.project_id, ResearchProjectRun.id)
        .join(ScanJob, ScanJob.id == ResearchProjectRun.scan_id)
        .where(
            ResearchProjectRun.lineage_complete.is_(True),
            ScanJob.status == "completed",
        )
        .order_by(ResearchProjectRun.project_id, ResearchProjectRun.sequence)
    ).all()
    for project_id, run_id in comparable_runs:
        resources.append(
            {
                "uri": f"tasksignal://projects/{project_id}/runs/{run_id}/delta",
                "name": f"Run delta {run_id}",
                "description": "Redacted immutable research run delta.",
                "mime_type": JSON_MIME_TYPE,
            }
        )
    thread_ids = db.scalars(select(OpportunityThread.id).order_by(OpportunityThread.id)).all()
    for thread_id in thread_ids:
        resources.append(
            {
                "uri": f"tasksignal://opportunity-threads/{thread_id}",
                "name": f"Opportunity thread {thread_id}",
                "description": "Redacted opportunity thread and snapshot history.",
                "mime_type": JSON_MIME_TYPE,
            }
        )
    packets = db.scalars(select(BuildPacket).order_by(BuildPacket.id)).all()
    for packet in packets:
        for artifact_name in sorted(_packet_files(packet)):
            resources.append(
                {
                    "uri": (
                        f"tasksignal://build-packets/{packet.id}/artifacts/"
                        f"{quote(artifact_name, safe='')}"
                    ),
                    "name": artifact_name,
                    "description": f"Build packet {packet.id} artifact.",
                    "mime_type": _artifact_mime_type(artifact_name),
                }
            )
    return resources


def _resource_parts(uri: str) -> tuple[str, list[str]]:
    if (
        not isinstance(uri, str)
        or not uri
        or uri != uri.strip()
        or any(character.isspace() or ord(character) < 32 for character in uri)
    ):
        raise McpReadError("invalid_resource_uri", "Resource URI is invalid.")
    try:
        parsed = urlsplit(uri)
    except ValueError as exc:
        raise McpReadError("invalid_resource_uri", "Resource URI is invalid.") from exc
    if (
        parsed.scheme != "tasksignal"
        or not parsed.netloc
        or "@" in parsed.netloc
        or ":" in parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.geturl() != uri
    ):
        raise McpReadError("invalid_resource_uri", "Resource URI is invalid.")
    try:
        decoded_path = unquote(parsed.path, errors="strict")
    except UnicodeError as exc:
        raise McpReadError("invalid_resource_uri", "Resource URI is invalid.") from exc
    parts = decoded_path.split("/")[1:]
    if any(
        not part
        or part in {".", ".."}
        or "\\" in part
        or any(character.isspace() or ord(character) < 32 for character in part)
        for part in parts
    ):
        raise McpReadError("invalid_resource_uri", "Resource URI is invalid.")
    return parsed.netloc, parts


def resolve_resource(db: Session, uri: str) -> dict[str, str]:
    """Resolve an exact allowlisted TaskSignal URI to safe UTF-8 content."""

    authority, parts = _resource_parts(uri)
    if authority == "projects" and len(parts) == 4 and parts[1] == "runs" and parts[3] == "delta":
        project_id = _identifier(parts[0], "project_id", resource=True)
        run_id = _identifier(parts[2], "run_id", resource=True)
        payload = compare_project_runs(db, project_id, run_id)
        return {
            "uri": uri,
            "name": f"Run delta {run_id}",
            "mime_type": JSON_MIME_TYPE,
            "text": _canonical_json(payload),
        }
    if authority == "opportunity-threads" and len(parts) == 1:
        thread_id = _identifier(parts[0], "thread_id", resource=True)
        payload = get_opportunity_thread(db, thread_id)
        return {
            "uri": uri,
            "name": f"Opportunity thread {thread_id}",
            "mime_type": JSON_MIME_TYPE,
            "text": _canonical_json(payload),
        }
    if authority == "build-packets" and len(parts) >= 3 and parts[1] == "artifacts":
        packet_id = _identifier(parts[0], "packet_id", resource=True)
        artifact_name = "/".join(parts[2:])
        if len(artifact_name) > _MAX_ARTIFACT_NAME_LENGTH:
            raise McpReadError("invalid_resource_uri", "Resource URI is invalid.")
        packet = db.get(BuildPacket, packet_id)
        if packet is None:
            raise McpReadError("not_found", "Build packet not found.")
        files = _packet_files(packet)
        content = files.get(artifact_name)
        if content is None:
            raise McpReadError("not_found", "Build packet artifact not found.")
        return {
            "uri": uri,
            "name": artifact_name,
            "mime_type": _artifact_mime_type(artifact_name),
            "text": content,
        }
    raise McpReadError("invalid_resource_uri", "Resource URI is invalid.")
