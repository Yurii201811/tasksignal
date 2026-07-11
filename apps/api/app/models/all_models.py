import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings

if settings.database_url.startswith("sqlite"):
    EmbeddingColumn = JSON
else:
    try:
        from pgvector.sqlalchemy import Vector

        EmbeddingColumn = Vector(384)
    except Exception:  # pragma: no cover - test fallback when pgvector is absent
        EmbeddingColumn = JSON

from app.db.base import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    status: Mapped[str] = mapped_column(Text)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    items_saved: Mapped[int] = mapped_column(Integer, default=0)
    signals_detected: Mapped[int] = mapped_column(Integer, default=0)
    clusters_created: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_created: Mapped[int] = mapped_column(Integer, default=0)
    outcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source | None] = relationship()
    research_run: Mapped["ResearchProjectRun | None"] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    observed_items: Mapped[list["ScanItem"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def source_type(self) -> str | None:
        return self.source.type if self.source else None

    @property
    def source_name(self) -> str | None:
        return self.source.name if self.source else None


class ResearchProject(Base):
    __tablename__ = "research_projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(Text, index=True)
    query: Mapped[str] = mapped_column(Text, default="")
    limit: Mapped[int] = mapped_column(Integer, default=30)
    cadence: Mapped[str] = mapped_column(Text, default="manual")
    schedule_interval_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    labels_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scan_jobs.id"),
        nullable=True,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    last_scan: Mapped[ScanJob | None] = relationship()
    runs: Mapped[list["ResearchProjectRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ResearchProjectRun.sequence",
    )
    opportunity_threads: Mapped[list["OpportunityThread"]] = relationship(
        back_populates="project",
        passive_deletes=True,
    )

    @property
    def last_scan_status(self) -> str | None:
        return self.last_scan.status if self.last_scan else None

    @property
    def labels(self) -> list[str]:
        return self.labels_json


class ResearchProjectRun(Base):
    __tablename__ = "research_project_runs"
    __table_args__ = (
        CheckConstraint("sequence > 0", name="ck_research_project_runs_sequence_positive"),
        CheckConstraint(
            "requested_limit BETWEEN 1 AND 100",
            name="ck_research_project_runs_requested_limit",
        ),
        UniqueConstraint(
            "project_id",
            "sequence",
            name="uq_research_project_runs_project_sequence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE"),
        index=True,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(Text)
    query: Mapped[str] = mapped_column(Text)
    requested_limit: Mapped[int] = mapped_column(Integer)
    lineage_complete: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    project: Mapped[ResearchProject] = relationship(back_populates="runs")
    scan: Mapped[ScanJob] = relationship(back_populates="research_run")


class LocalWorkspaceSettings(Base):
    __tablename__ = "local_workspace_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    owner_name: Mapped[str] = mapped_column(Text, default="")
    workspace_goal: Mapped[str] = mapped_column(Text, default="")
    default_source_type: Mapped[str] = mapped_column(Text, default="hackernews")
    default_query: Mapped[str] = mapped_column(Text, default="ask")
    default_limit: Mapped[int] = mapped_column(Integer, default=30)
    default_cadence: Mapped[str] = mapped_column(Text, default="manual")
    default_schedule_interval_hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    @property
    def configured(self) -> bool:
        return bool(self.owner_name.strip() or self.workspace_goal.strip())


class RawItem(Base):
    __tablename__ = "raw_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(Text)
    raw_json: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class NormalizedItem(Base):
    __tablename__ = "normalized_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(Text, index=True)
    external_id: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    author_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    text_hash: Mapped[str] = mapped_column(Text, unique=True, index=True)
    language: Mapped[str] = mapped_column(Text, default="en")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    signal: Mapped["ItemSignal"] = relationship(back_populates="item", cascade="all,delete")
    embedding: Mapped["ItemEmbedding"] = relationship(back_populates="item", cascade="all,delete")
    scan_observations: Mapped[list["ScanItem"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ScanItem(Base):
    __tablename__ = "scan_items"
    __table_args__ = (Index("ix_scan_items_item_scan", "item_id", "scan_id"),)

    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("normalized_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_in_scan: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
    )

    scan: Mapped[ScanJob] = relationship(back_populates="observed_items")
    item: Mapped[NormalizedItem] = relationship(back_populates="scan_observations")


class ItemSignal(Base):
    __tablename__ = "item_signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("normalized_items.id"), index=True)
    is_problem_signal: Mapped[bool] = mapped_column(Boolean, index=True)
    signal_type: Mapped[str] = mapped_column(Text, index=True)
    pain_score: Mapped[float] = mapped_column(Float)
    task_concreteness_score: Mapped[float] = mapped_column(Float)
    buying_intent_score: Mapped[float] = mapped_column(Float)
    evidence_spans_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    classifier_version: Mapped[str] = mapped_column(Text, default="rules-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    item: Mapped[NormalizedItem] = relationship(back_populates="signal")


class ItemEmbedding(Base):
    __tablename__ = "item_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("normalized_items.id"), index=True)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingColumn)
    model_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    item: Mapped[NormalizedItem] = relationship(back_populates="embedding")


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scan_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    centroid_embedding: Mapped[list[float] | None] = mapped_column(EmbeddingColumn, nullable=True)
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ClusterItem(Base):
    __tablename__ = "cluster_items"

    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clusters.id"), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("normalized_items.id"), primary_key=True)
    similarity_score: Mapped[float] = mapped_column(Float)


class OpportunityThread(Base):
    __tablename__ = "opportunity_threads"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_opportunity_threads_version_positive"),
        CheckConstraint(
            "lineage_status IN ('complete', 'untracked')",
            name="ck_opportunity_threads_lineage_status",
        ),
        CheckConstraint(
            "review_state IN ('new', 'needs_more_evidence', 'promising', "
            "'rejected', 'duplicate', 'build_candidate')",
            name="ck_opportunity_threads_review_state",
        ),
        CheckConstraint(
            "(project_id IS NULL AND lineage_status = 'untracked') OR "
            "(project_id IS NOT NULL AND lineage_status = 'complete')",
            name="ck_opportunity_threads_project_lineage",
        ),
        Index("ix_opportunity_threads_project_review", "project_id", "review_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_projects.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    current_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "opportunities.id",
            name="fk_opportunity_threads_current_snapshot_id_opportunities",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
        unique=True,
    )
    lineage_status: Mapped[str] = mapped_column(Text)
    review_state: Mapped[str] = mapped_column(Text, default="new", server_default="new", index=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    project: Mapped[ResearchProject | None] = relationship(back_populates="opportunity_threads")
    current_snapshot: Mapped["Opportunity | None"] = relationship(
        foreign_keys=[current_snapshot_id],
        post_update=True,
    )
    snapshots: Mapped[list["Opportunity"]] = relationship(
        back_populates="thread",
        foreign_keys="Opportunity.thread_id",
    )
    decision_events: Mapped[list["OpportunityDecisionEvent"]] = relationship(
        back_populates="thread",
        foreign_keys="OpportunityDecisionEvent.thread_id",
        order_by="OpportunityDecisionEvent.created_at",
    )


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            "match_method IN ('legacy_backfill', 'new_untracked', "
            "'new_no_candidates', 'new_below_threshold', 'new_ambiguous', "
            "'exact_evidence', 'weighted_similarity', 'manual_detach', "
            "'regenerated', 'enhanced')",
            name="ck_opportunities_match_method",
        ),
        CheckConstraint(
            "match_confidence IS NULL OR "
            "(match_confidence >= 0 AND match_confidence <= 1)",
            name="ck_opportunities_match_confidence",
        ),
        CheckConstraint(
            "match_margin IS NULL OR (match_margin >= 0 AND match_margin <= 1)",
            name="ck_opportunities_match_margin",
        ),
        CheckConstraint(
            "centroid_similarity IS NULL OR "
            "(centroid_similarity >= 0 AND centroid_similarity <= 1)",
            name="ck_opportunities_centroid_similarity",
        ),
        CheckConstraint(
            "evidence_jaccard IS NULL OR "
            "(evidence_jaccard >= 0 AND evidence_jaccard <= 1)",
            name="ck_opportunities_evidence_jaccard",
        ),
        CheckConstraint(
            "title_jaccard IS NULL OR (title_jaccard >= 0 AND title_jaccard <= 1)",
            name="ck_opportunities_title_jaccard",
        ),
        CheckConstraint(
            "(embedding_model IS NULL AND embedding_backend IS NULL) OR "
            "(embedding_model IS NOT NULL AND embedding_backend IS NOT NULL)",
            name="ck_opportunities_embedding_identity",
        ),
        Index("ix_opportunities_thread_created", "thread_id", "created_at", "id"),
        Index("ix_opportunities_run_thread", "run_id", "thread_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("opportunity_threads.id", ondelete="RESTRICT"),
        index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_project_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scan_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_hash: Mapped[str] = mapped_column(Text, index=True)
    content_hash: Mapped[str] = mapped_column(Text)
    match_method: Mapped[str] = mapped_column(Text)
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_jaccard: Mapped[float | None] = mapped_column(Float, nullable=True)
    title_jaccard: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_backend: Mapped[str | None] = mapped_column(Text, nullable=True)
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clusters.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    problem_statement: Mapped[str] = mapped_column(Text)
    target_user: Mapped[str] = mapped_column(Text)
    current_workaround: Mapped[str] = mapped_column(Text)
    suggested_mvp: Mapped[str] = mapped_column(Text)
    why_now: Mapped[str] = mapped_column(Text)
    feasibility_score: Mapped[float] = mapped_column(Float)
    opportunity_score: Mapped[float] = mapped_column(Float, index=True)
    competition_notes: Mapped[str] = mapped_column(Text)
    scoring_breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_prompt: Mapped[str] = mapped_column(Text)
    review_state: Mapped[str] = mapped_column(
        Text,
        default="new",
        server_default="new",
        index=True,
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    thread: Mapped[OpportunityThread] = relationship(
        back_populates="snapshots",
        foreign_keys=[thread_id],
    )
    research_run: Mapped[ResearchProjectRun | None] = relationship()


class OpportunityDecisionEvent(Base):
    __tablename__ = "opportunity_decision_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('legacy_backfill', 'decision_changed', "
            "'snapshot_detached', 'thread_created_by_detach')",
            name="ck_opportunity_decision_events_type",
        ),
        CheckConstraint(
            "actor_type IN ('system', 'human', 'agent')",
            name="ck_opportunity_decision_events_actor",
        ),
        Index(
            "ix_opportunity_decision_events_thread_created",
            "thread_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("opportunity_threads.id", ondelete="RESTRICT"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_thread_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opportunity_threads.id", ondelete="SET NULL"),
        nullable=True,
    )
    previous_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    thread: Mapped[OpportunityThread] = relationship(
        back_populates="decision_events",
        foreign_keys=[thread_id],
    )


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("normalized_items.id"), index=True)
    label: Mapped[str] = mapped_column(Text)
    user_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
