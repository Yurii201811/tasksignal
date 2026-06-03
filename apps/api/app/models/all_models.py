import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, Text
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

    source: Mapped[Source | None] = relationship()

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

    @property
    def last_scan_status(self) -> str | None:
        return self.last_scan.status if self.last_scan else None

    @property
    def labels(self) -> list[str]:
        return self.labels_json


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


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("normalized_items.id"), index=True)
    label: Mapped[str] = mapped_column(Text)
    user_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
