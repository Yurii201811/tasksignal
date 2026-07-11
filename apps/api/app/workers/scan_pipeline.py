from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from time import sleep
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.all_models import (
    Cluster,
    ClusterItem,
    DiscourseSourceState,
    ItemEmbedding,
    ItemSignal,
    NormalizedItem,
    RawItem,
    ResearchProject,
    ResearchProjectRun,
    ScanItem,
    ScanJob,
    Source,
)
from app.services.clustering.service import cluster_items
from app.services.detection.rules import detect_problem_signal
from app.services.discourse_sources.service import (
    discourse_readiness,
    record_discourse_failure,
    record_discourse_success,
)
from app.services.embeddings.service import EmbeddingService, cosine_similarity
from app.services.generation.service import generate_opportunity
from app.services.ingestion.connectors import (
    BaseConnector,
    DiscourseConnector,
    DiscourseConnectorError,
    FixtureConnector,
    GitHubIssuesConnector,
    HackerNewsConnector,
    RedditConnector,
    StackExchangeConnector,
    connector_display_name,
    connector_failure_message,
    without_raw_author,
)
from app.services.ingestion.normalization import normalize
from app.services.ingestion.types import RawFetchedItem
from app.services.opportunity_threads.service import attach_generated_snapshot
from app.services.research_projects.service import mark_latest_project_run
from app.services.scoring.service import score_opportunity

ConnectorFactory = Callable[[], BaseConnector]

SOURCE_ALIASES = {
    "fixture": "fixture",
    "fixtures": "fixture",
    "github": "github",
    "github_issues": "github",
    "github-issues": "github",
    "hacker-news": "hackernews",
    "hackernews": "hackernews",
    "hn": "hackernews",
    "reddit": "reddit",
    "discourse": "discourse",
    "stack-exchange": "stackexchange",
    "stack_exchange": "stackexchange",
    "stackexchange": "stackexchange",
    "stackoverflow": "stackexchange",
}

CONNECTOR_FACTORIES: dict[str, ConnectorFactory | None] = {
    "discourse": None,
    "fixture": FixtureConnector,
    "github": GitHubIssuesConnector,
    "hackernews": HackerNewsConnector,
    "reddit": RedditConnector,
    "stackexchange": StackExchangeConnector,
}

# Connector I/O remains concurrent. The process lock avoids needless local
# contention, while a transaction-scoped database lock below protects separate
# API workers and SQLite processes.
SCAN_WRITE_LOCK = RLock()
POSTGRES_SCAN_ADVISORY_LOCK_ID = 6071229765013788494


class ProjectVersionConflict(RuntimeError):
    """Raised before scan reservation when an expected project version is stale."""


@dataclass(frozen=True)
class ScanPipelineResult:
    raw_items_loaded: int
    normalized_items_created: int
    signals_detected: int
    clusters_created: int
    opportunities_created: int


@dataclass(frozen=True)
class ObservedItemIdentity:
    source: str
    external_id: str
    url: str


@dataclass(frozen=True)
class SavedFetchedItems:
    observed_item_ids: list[UUID]
    created_item_ids: list[UUID]
    identities_by_item_id: dict[UUID, ObservedItemIdentity]


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors_by_item: dict[UUID, list[float]]
    model_name: str
    backend: str


def acquire_database_scan_write_lock(db: Session) -> None:
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        if not db.in_transaction():
            db.execute(text("BEGIN IMMEDIATE"))
        return
    if dialect == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": POSTGRES_SCAN_ADVISORY_LOCK_ID},
        )


def acquire_database_scan_write_lock_with_retry(
    db: Session,
    *,
    attempts: int = 3,
) -> None:
    for attempt in range(attempts):
        try:
            acquire_database_scan_write_lock(db)
            return
        except OperationalError as exc:
            is_sqlite_busy = (
                db.get_bind().dialect.name == "sqlite"
                and "locked" in str(exc).lower()
            )
            db.rollback()
            if not is_sqlite_busy or attempt == attempts - 1:
                raise
            sleep(0.05 * (2**attempt))


def scan_outcome_message(result: ScanPipelineResult) -> str:
    if result.raw_items_loaded == 0:
        return (
            "The connector returned no records. Try a broader query, a different feed, "
            "or a larger limit before judging the source."
        )
    if result.normalized_items_created == 0:
        if result.opportunities_created:
            return (
                "All observed evidence was seen before. The scan created a fresh "
                f"snapshot with {result.opportunities_created} ranked "
                f"{'opportunity' if result.opportunities_created == 1 else 'opportunities'}."
            )
        return (
            "The scan completed with no new evidence. Returned records were empty or "
            "seen before; absence is not treated as deletion or resolution."
        )
    if result.signals_detected == 0:
        return (
            "The scan saved public records but did not detect concrete problem or task "
            "signals. Try a more pain-oriented query such as 'manual workflow', "
            "'broken onboarding', or 'github actions failed'."
        )
    if result.opportunities_created == 0:
        return (
            "The scan found problem signals but not enough related evidence to form a "
            "ranked opportunity. Try a narrower workflow query or increase the limit."
        )
    return (
        f"The scan generated {result.opportunities_created} ranked "
        f"{'opportunity' if result.opportunities_created == 1 else 'opportunities'} "
        f"from {result.signals_detected} detected "
        f"{'signal' if result.signals_detected == 1 else 'signals'}."
    )


def canonical_source(source: str) -> str:
    normalized = source.strip().lower().replace(" ", "-")
    return SOURCE_ALIASES.get(normalized, normalized)


def connector_for_source(
    source: str,
    *,
    db: Session | None = None,
    source_id: UUID | None = None,
) -> BaseConnector:
    source_type = canonical_source(source)
    if source_type == "discourse":
        if db is None or source_id is None:
            raise ValueError("Discourse scans require an authorized source_id.")
        source_record = db.get(Source, source_id)
        state = db.get(DiscourseSourceState, source_id)
        if source_record is None or canonical_source(source_record.type) != "discourse":
            raise ValueError("Configured Discourse source was not found.")
        readiness = discourse_readiness(source_record, state)
        if not readiness.can_run or state is None:
            raise ValueError(
                f"Discourse source is not ready: {readiness.status.replace('_', ' ')}."
            )
        return DiscourseConnector(state.origin)

    factory = CONNECTOR_FACTORIES.get(source_type)
    if factory is None:
        supported = ", ".join(sorted(CONNECTOR_FACTORIES))
        raise ValueError(f"Unsupported source '{source}'. Supported sources: {supported}.")
    return factory()


def ensure_source(
    db: Session,
    source_type: str,
    source_id: UUID | None = None,
) -> Source:
    if source_id is not None:
        source = db.get(Source, source_id)
        if source is None or canonical_source(source.type) != source_type:
            raise ValueError("Configured source does not match the requested connector.")
        return source
    if source_type == "discourse":
        raise ValueError("Discourse scans require an authorized source_id.")
    source = db.scalar(select(Source).where(Source.type == source_type))
    if source is not None:
        return source

    source = Source(
        name=connector_display_name(source_type),
        type=source_type,
        config_json={},
        enabled=source_type != "fixture",
    )
    db.add(source)
    db.flush()
    return source


def discourse_failure_code(category: str) -> str:
    return {
        "timeout": "timeout",
        "network_error": "connection",
        "unsafe_configuration": "dns_rejected",
        "unsafe_target": "dns_rejected",
        "unsafe_redirect": "redirect_rejected",
        "too_many_redirects": "redirect_rejected",
        "rate_limited": "rate_limited",
        "http_error": "http_error",
        "response_too_large": "response_too_large",
        "malformed_response": "invalid_response",
    }.get(category, "invalid_response")


def save_fetched_items(db: Session, fetched: list[RawFetchedItem]) -> SavedFetchedItems:
    observed_item_ids: list[UUID] = []
    created_item_ids: list[UUID] = []
    identities_by_item_id: dict[UUID, ObservedItemIdentity] = {}
    for raw in fetched:
        raw_exists = db.scalar(
            select(RawItem.id).where(
                RawItem.source == raw.source,
                RawItem.external_id == raw.external_id,
            )
        )
        if raw_exists is None:
            db.add(
                RawItem(
                    source=raw.source,
                    external_id=raw.external_id,
                    raw_json=without_raw_author(raw.source, raw.raw_json),
                    fetched_at=raw.fetched_at,
                )
            )

        normalized = normalize(raw)
        if not normalized["title"] and not normalized["body"]:
            continue
        exists = db.scalar(
            select(NormalizedItem.id).where(
                NormalizedItem.text_hash == normalized["text_hash"]
            )
        )
        if exists is not None:
            if exists not in observed_item_ids:
                observed_item_ids.append(exists)
                identities_by_item_id[exists] = ObservedItemIdentity(
                    source=normalized["source"],
                    external_id=normalized["external_id"],
                    url=normalized["url"],
                )
            continue

        item = NormalizedItem(**normalized)
        db.add(item)
        db.flush()
        observed_item_ids.append(item.id)
        created_item_ids.append(item.id)
        identities_by_item_id[item.id] = ObservedItemIdentity(
            source=normalized["source"],
            external_id=normalized["external_id"],
            url=normalized["url"],
        )
    return SavedFetchedItems(
        observed_item_ids=observed_item_ids,
        created_item_ids=created_item_ids,
        identities_by_item_id=identities_by_item_id,
    )


def record_scan_items(
    db: Session,
    scan_id: UUID,
    saved: SavedFetchedItems,
) -> None:
    created_ids = set(saved.created_item_ids)
    for item_id in saved.observed_item_ids:
        identity = saved.identities_by_item_id[item_id]
        db.add(
            ScanItem(
                scan_id=scan_id,
                item_id=item_id,
                created_in_scan=item_id in created_ids,
                observed_source=identity.source,
                observed_external_id=identity.external_id,
                observed_url=identity.url,
            )
        )
    db.flush()


def detect_signals(db: Session, item_ids: list[UUID]) -> int:
    if not item_ids:
        return 0

    items = db.scalars(select(NormalizedItem).where(NormalizedItem.id.in_(item_ids))).all()
    for item in items:
        existing = db.scalar(select(ItemSignal.id).where(ItemSignal.item_id == item.id))
        if existing is not None:
            continue

        result = detect_problem_signal(item.title, item.body)
        db.add(
            ItemSignal(
                item_id=item.id,
                is_problem_signal=result.is_problem_signal,
                signal_type=result.signal_type,
                pain_score=result.pain_score,
                task_concreteness_score=result.task_concreteness_score,
                buying_intent_score=result.buying_intent_score,
                evidence_spans_json=result.evidence_spans,
                classifier_version="rules-v1",
            )
        )
    db.flush()
    return len(
        db.scalars(
            select(ItemSignal.id).where(
                ItemSignal.item_id.in_(item_ids),
                ItemSignal.is_problem_signal.is_(True),
            )
        ).all()
    )


def embed_signals(
    db: Session,
    signal_rows: list[tuple[NormalizedItem, ItemSignal]],
) -> EmbeddingBatch:
    embedder = EmbeddingService()
    embedding_model = f"{embedder.model_name}:{embedder.backend}"
    item_ids = [item.id for item, _signal in signal_rows]
    stored = db.scalars(
        select(ItemEmbedding).where(ItemEmbedding.item_id.in_(item_ids))
    ).all()
    stored_by_item: dict[UUID, ItemEmbedding] = {}
    embeddings_by_item: dict[UUID, list[float]] = {}
    for row in stored:
        stored_by_item.setdefault(row.item_id, row)
        if row.model_name == embedding_model:
            stored_by_item[row.item_id] = row
            embeddings_by_item[row.item_id] = list(row.embedding)

    missing_rows = [row for row in signal_rows if row[0].id not in embeddings_by_item]
    if missing_rows:
        texts = [f"{item.title}. {item.body}" for item, _signal in missing_rows]
        vectors = embedder.embed_texts(texts)
        for (item, _signal), vector in zip(missing_rows, vectors, strict=True):
            embeddings_by_item[item.id] = vector
            stored_embedding = stored_by_item.get(item.id)
            if stored_embedding is None:
                db.add(
                    ItemEmbedding(
                        item_id=item.id,
                        embedding=vector,
                        model_name=embedding_model,
                    )
                )
            else:
                stored_embedding.embedding = vector
                stored_embedding.model_name = embedding_model
    db.flush()
    return EmbeddingBatch(
        vectors_by_item=embeddings_by_item,
        model_name=embedder.model_name,
        backend=embedder.backend,
    )


def generate_clusters_and_opportunities(
    db: Session,
    signal_rows: list[tuple[NormalizedItem, ItemSignal]],
    embedding_batch: EmbeddingBatch,
    scan_id: UUID | None = None,
) -> tuple[int, int]:
    embeddings_by_item = embedding_batch.vectors_by_item
    cluster_inputs = [
        {
            "id": item.id,
            "source": item.source,
            "url": item.url,
            "title": item.title,
            "body": item.body,
            "created_at": item.created_at,
            "signal_type": signal.signal_type,
            "pain_score": signal.pain_score,
            "task_concreteness_score": signal.task_concreteness_score,
            "buying_intent_score": signal.buying_intent_score,
            "evidence_spans": signal.evidence_spans_json,
        }
        for item, signal in signal_rows
    ]
    candidates = cluster_items(cluster_inputs, embeddings_by_item)
    item_lookup = {entry["id"]: entry for entry in cluster_inputs}
    clusters_created = 0
    opportunities_created = 0

    for candidate in candidates:
        cluster = Cluster(
            scan_id=scan_id,
            title=candidate.title,
            summary=candidate.summary,
            centroid_embedding=candidate.centroid,
            size=len(candidate.item_ids),
        )
        db.add(cluster)
        db.flush()
        clusters_created += 1

        group_items = [item_lookup[item_id] for item_id in candidate.item_ids]
        for item_id in candidate.item_ids:
            db.add(
                ClusterItem(
                    cluster_id=cluster.id,
                    item_id=item_id,
                    similarity_score=cosine_similarity(
                        candidate.centroid, embeddings_by_item[item_id]
                    ),
                )
            )
        db.flush()

        score = score_opportunity(group_items, f"{candidate.title} {candidate.summary}")
        generated = generate_opportunity(candidate.title, candidate.summary, group_items, score)
        attach_generated_snapshot(
            db,
            cluster=cluster,
            scan_id=scan_id,
            embedding_model=embedding_batch.model_name,
            embedding_backend=embedding_batch.backend,
            opportunity_values={
                "title": generated["title"],
                "problem_statement": generated["problem_statement"],
                "target_user": generated["target_user"],
                "current_workaround": generated["current_workaround"],
                "suggested_mvp": generated["suggested_mvp"],
                "why_now": generated["why_now"],
                "feasibility_score": generated["feasibility_score"],
                "opportunity_score": generated["opportunity_score"],
                "competition_notes": generated["competition_notes"],
                "scoring_breakdown_json": {
                    **score,
                    "common_phrases": generated["common_phrases"],
                },
                "generated_prompt": generated["generated_prompt"],
            },
        )
        opportunities_created += 1

    db.flush()
    return clusters_created, opportunities_created


def process_fetched_items(
    db: Session,
    fetched: list[RawFetchedItem],
    scan_id: UUID | None = None,
) -> ScanPipelineResult:
    saved = save_fetched_items(db, fetched)
    if scan_id is not None:
        record_scan_items(db, scan_id, saved)
    signals_detected = detect_signals(db, saved.observed_item_ids)

    if not saved.observed_item_ids:
        return ScanPipelineResult(
            raw_items_loaded=len(fetched),
            normalized_items_created=0,
            signals_detected=0,
            clusters_created=0,
            opportunities_created=0,
        )

    signal_rows = db.execute(
        select(NormalizedItem, ItemSignal)
        .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id)
        .where(
            NormalizedItem.id.in_(saved.observed_item_ids),
            ItemSignal.is_problem_signal.is_(True),
        )
    ).all()
    if not signal_rows:
        return ScanPipelineResult(
            raw_items_loaded=len(fetched),
            normalized_items_created=len(saved.created_item_ids),
            signals_detected=signals_detected,
            clusters_created=0,
            opportunities_created=0,
        )

    embedding_batch = embed_signals(db, signal_rows)
    clusters_created, opportunities_created = generate_clusters_and_opportunities(
        db,
        signal_rows,
        embedding_batch,
        scan_id=scan_id,
    )
    return ScanPipelineResult(
        raw_items_loaded=len(fetched),
        normalized_items_created=len(saved.created_item_ids),
        signals_detected=signals_detected,
        clusters_created=clusters_created,
        opportunities_created=opportunities_created,
    )


def run_scan_pipeline(
    db: Session,
    connector: BaseConnector,
    query: str,
    limit: int,
    scan_id: UUID | None = None,
) -> ScanPipelineResult:
    fetched = connector.fetch(query=query, limit=limit)
    with SCAN_WRITE_LOCK:
        acquire_database_scan_write_lock_with_retry(db)
        return process_fetched_items(db, fetched, scan_id=scan_id)


def create_research_project_run(
    db: Session,
    project: ResearchProject,
    scan: ScanJob,
    source_type: str,
    query: str,
    requested_limit: int,
    source_origin: str | None = None,
) -> ResearchProjectRun:
    last_sequence = db.scalar(
        select(func.max(ResearchProjectRun.sequence)).where(
            ResearchProjectRun.project_id == project.id
        )
    )
    run = ResearchProjectRun(
        project_id=project.id,
        scan_id=scan.id,
        sequence=(last_sequence or 0) + 1,
        source_type=source_type,
        query=query,
        requested_limit=requested_limit,
        source_origin=source_origin,
        lineage_complete=False,
    )
    db.add(run)
    return run


def reserve_scan_job(
    db: Session,
    *,
    source_type: str,
    query: str,
    requested_limit: int,
    research_project_id: UUID | None,
    configured_source_id: UUID | None = None,
    expected_project_version: int | None = None,
    scan_id: UUID | None = None,
) -> tuple[ScanJob, ResearchProjectRun | None]:
    for attempt in range(3):
        try:
            with SCAN_WRITE_LOCK:
                db.commit()
                acquire_database_scan_write_lock_with_retry(db)
                locked_project = None
                if research_project_id is not None:
                    locked_project = db.scalar(
                        select(ResearchProject)
                        .where(ResearchProject.id == research_project_id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                    if locked_project is None:
                        raise ValueError("Research project no longer exists")
                    if (
                        expected_project_version is not None
                        and locked_project.version != expected_project_version
                    ):
                        raise ProjectVersionConflict(
                            "Research project version conflict: "
                            f"expected {expected_project_version}, current {locked_project.version}."
                        )

                source_record = ensure_source(
                    db,
                    source_type,
                    source_id=configured_source_id,
                )
                source_origin = (
                    source_record.discourse_state.origin
                    if source_type == "discourse"
                    and source_record.discourse_state is not None
                    else None
                )
                job_values = {
                    "source_id": source_record.id,
                    "status": "queued",
                    "query": query,
                    "items_found": 0,
                    "items_saved": 0,
                }
                if scan_id is not None:
                    job_values["id"] = scan_id
                job = ScanJob(
                    **job_values,
                )
                db.add(job)
                db.flush()
                research_run = None
                if locked_project is not None:
                    research_run = create_research_project_run(
                        db,
                        project=locked_project,
                        scan=job,
                        source_type=source_type,
                        query=query,
                        requested_limit=requested_limit,
                        source_origin=source_origin,
                    )
                    locked_project.run_count += 1
                    locked_project.version += 1
                    locked_project.updated_at = datetime.now(UTC)
                db.commit()
                return job, research_run
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise
    raise RuntimeError("Unable to reserve scan job")  # pragma: no cover


def process_scan(
    db: Session,
    source: str,
    query: str = "",
    limit: int = 30,
    connector: BaseConnector | None = None,
    research_project: ResearchProject | None = None,
    source_id: UUID | None = None,
    expected_project_version: int | None = None,
    scan_id: UUID | None = None,
    before_persist: Callable[[Session], None] | None = None,
) -> ScanJob:
    source_type = canonical_source(source)
    requested_limit = max(1, min(limit, 100))
    research_project_id = research_project.id if research_project is not None else None
    configured_source_id = (
        research_project.source_id if research_project is not None else source_id
    )
    job, research_run = reserve_scan_job(
        db,
        source_type=source_type,
        query=query,
        requested_limit=requested_limit,
        research_project_id=research_project_id,
        configured_source_id=configured_source_id,
        expected_project_version=expected_project_version,
        scan_id=scan_id,
    )
    research_run_sequence = research_run.sequence if research_run is not None else None

    try:
        with SCAN_WRITE_LOCK:
            job.status = "running"
            job.started_at = datetime.now(UTC)
            db.commit()

        active_connector = connector or connector_for_source(
            source_type,
            db=db,
            source_id=configured_source_id,
        )
        if isinstance(active_connector, DiscourseConnector):
            fetch_result = active_connector.fetch_result(
                query=query,
                limit=requested_limit,
            )
            fetched = fetch_result.items
            success_at = fetch_result.last_success_at
            success_retry_after = fetch_result.retry_after_seconds
        else:
            fetched = active_connector.fetch(query=query, limit=requested_limit)
            success_at = datetime.now(UTC)
            success_retry_after = None

        if source_type == "discourse" and configured_source_id is not None:
            with SCAN_WRITE_LOCK:
                acquire_database_scan_write_lock_with_retry(db)
                discourse_state = db.get(
                    DiscourseSourceState,
                    configured_source_id,
                )
                if discourse_state is not None:
                    retry_after = (
                        str(success_retry_after)
                        if success_retry_after is not None
                        else None
                    )
                    record_discourse_success(
                        discourse_state,
                        at=success_at,
                        retry_after=retry_after,
                    )
                    db.commit()

        with SCAN_WRITE_LOCK:
            try:
                acquire_database_scan_write_lock_with_retry(db)
                if before_persist is not None:
                    before_persist(db)
                result = process_fetched_items(db, fetched, scan_id=job.id)
                job.status = "completed"
                job.finished_at = datetime.now(UTC)
                job.items_found = result.raw_items_loaded
                job.items_saved = result.normalized_items_created
                job.signals_detected = result.signals_detected
                job.clusters_created = result.clusters_created
                job.opportunities_created = result.opportunities_created
                job.outcome_message = scan_outcome_message(result)
                job.error_message = None
                if research_run is not None:
                    research_run.lineage_complete = True
                    mark_latest_project_run(
                        db,
                        project_id=research_run.project_id,
                        run_sequence=research_run.sequence,
                        scan_id=job.id,
                        finished_at=job.finished_at,
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return job
    except Exception as exc:
        with SCAN_WRITE_LOCK:
            db.rollback()
            acquire_database_scan_write_lock_with_retry(db)
            if (
                source_type == "discourse"
                and configured_source_id is not None
                and isinstance(exc, DiscourseConnectorError)
            ):
                discourse_state = db.get(
                    DiscourseSourceState,
                    configured_source_id,
                )
                if discourse_state is not None:
                    retry_after = (
                        str(exc.info.retry_after_seconds)
                        if exc.info.retry_after_seconds is not None
                        else None
                    )
                    record_discourse_failure(
                        discourse_state,
                        code=discourse_failure_code(exc.info.category),
                        message=exc.info.message,
                        http_status=exc.info.status_code,
                        retry_after=retry_after,
                    )
            failed_job = db.get(ScanJob, job.id)
            if failed_job is None:
                raise
            failed_job.status = "failed"
            failed_job.finished_at = datetime.now(UTC)
            failed_job.error_message = connector_failure_message(source_type, exc)
            failed_job.outcome_message = (
                "The scan failed before a complete outcome could be computed."
            )
            if research_project_id is not None and research_run_sequence is not None:
                mark_latest_project_run(
                    db,
                    project_id=research_project_id,
                    run_sequence=research_run_sequence,
                    scan_id=failed_job.id,
                    finished_at=failed_job.finished_at,
                )
            db.commit()
        return failed_job
