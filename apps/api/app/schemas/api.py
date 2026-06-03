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
    signals_detected: int = 0
    clusters_created: int = 0
    opportunities_created: int = 0
    outcome_message: str | None = None
    model_config = ConfigDict(from_attributes=True)


class IntegrationOut(BaseModel):
    id: str
    name: str
    kind: str
    status: str
    credential_state: str
    public_scan_enabled: bool = False
    operator_token_required: bool = False
    required_env: list[str] = []
    optional_env: list[str] = []
    rate_limit_note: str
    privacy_note: str
    next_step: str
    last_scan_status: str | None = None
    last_scan_at: datetime | None = None


class IntegrationTestOut(BaseModel):
    id: str
    status: str
    detail: str
    items_found: int = 0


class ReadinessOut(BaseModel):
    status: str
    blockers: list[str] = []
    warnings: list[str] = []
    checks: dict


class LocalWorkspaceUpdate(BaseModel):
    owner_name: str = Field(default="", max_length=120)
    workspace_goal: str = Field(default="", max_length=300)
    default_source_type: str = Field(default="hackernews", max_length=60)
    default_query: str = Field(default="ask", max_length=300)
    default_limit: int = Field(default=30, ge=1, le=100)
    default_cadence: str = Field(default="manual", max_length=60)
    default_schedule_interval_hours: int | None = Field(default=None, ge=1, le=24 * 31)


class LocalWorkspaceOut(LocalWorkspaceUpdate):
    id: int
    configured: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResearchProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    source_type: str = "hackernews"
    query: str = Field(default="", max_length=300)
    limit: int = Field(default=30, ge=1, le=100)
    cadence: str = Field(default="manual", max_length=60)
    schedule_interval_hours: int | None = Field(default=None, ge=1, le=24 * 31)
    labels: list[str] = Field(default_factory=list, max_length=12)
    enabled: bool = True


class ResearchProjectOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    source_type: str
    query: str
    limit: int
    cadence: str
    schedule_interval_hours: int | None
    labels: list[str] = []
    enabled: bool
    last_scan_id: UUID | None
    last_scan_status: str | None = None
    last_run_at: datetime | None
    next_run_at: datetime | None
    run_count: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DueRunOut(BaseModel):
    ran: int
    skipped: int
    scans: list[ScanOut] = []


class EnhancementOut(BaseModel):
    provider: str
    model: str
    enhanced_prompt: str
    applied: bool = False


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


class TaskPackOut(BaseModel):
    opportunity_id: UUID
    title: str
    problem: str
    suggested_mvp: str
    codex_prompt: str
    markdown: str
    evidence_urls: list[str]
    acceptance_criteria: list[str]
    privacy_constraints: list[str]
