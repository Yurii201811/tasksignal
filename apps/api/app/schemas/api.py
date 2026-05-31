from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceCreate(BaseModel):
    name: str
    type: str
    config_json: dict = Field(default_factory=dict)
    enabled: bool = True


class SourceOut(SourceCreate):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScanCreate(BaseModel):
    source: str = "hackernews"
    query: str = ""
    limit: int = Field(default=30, ge=1, le=100)


class ScanOut(BaseModel):
    id: UUID
    source_id: UUID | None
    source_type: str | None = None
    source_name: str | None = None
    status: str
    query: str | None
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    items_found: int
    items_saved: int
    model_config = ConfigDict(from_attributes=True)


class ItemOut(BaseModel):
    id: UUID
    source: str
    external_id: str
    url: str
    title: str
    body: str
    score: int | None
    comments_count: int | None
    created_at: datetime
    tags: list[str]
    signal_type: str | None = None
    pain_score: float | None = None
    task_concreteness_score: float | None = None
    buying_intent_score: float | None = None
    evidence_spans: list[str] = []


class OpportunityOut(BaseModel):
    id: UUID
    cluster_id: UUID
    title: str
    problem_statement: str
    target_user: str
    current_workaround: str
    suggested_mvp: str
    why_now: str
    feasibility_score: float
    opportunity_score: float
    competition_notes: str
    scoring_breakdown_json: dict
    generated_prompt: str
    created_at: datetime
    updated_at: datetime
    evidence_items: list[ItemOut] = []
    signal_count: int = 0
    top_source: str = "fixture"
    model_config = ConfigDict(from_attributes=True)


class ProcessSummary(BaseModel):
    raw_items_loaded: int
    normalized_items_created: int
    signals_detected: int
    clusters_created: int
    opportunities_created: int


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class LabelCreate(BaseModel):
    item_id: UUID
    label: str
    user_note: str | None = None
