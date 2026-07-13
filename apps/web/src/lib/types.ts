export type Stats = {
  total_items: number;
  problem_signals: number;
  clusters: number;
  opportunities: number;
  source_breakdown: { source: string; count: number }[];
  pain_distribution: { bucket: string; count: number }[];
};

export type ProcessSummary = {
  raw_items_loaded: number;
  normalized_items_created: number;
  signals_detected: number;
  clusters_created: number;
  opportunities_created: number;
};

export type ReviewState =
  | "new"
  | "needs_more_evidence"
  | "promising"
  | "rejected"
  | "duplicate"
  | "build_candidate";

export type EvidenceReviewLabel =
  | "true_signal"
  | "false_positive"
  | "unclear"
  | "duplicate"
  | "not_actionable"
  | "sensitive_risk";

export type EvidenceReadinessLevel = "weak" | "medium" | "strong";

export type OpportunityFilters = {
  reviewState?: ReviewState;
  currentOnly?: boolean;
  projectId?: string;
  evidenceSource?: string;
  readiness?: EvidenceReadinessLevel;
  maxAgeDays?: number;
};

export type EvidenceReadinessCheck =
  | "enough_evidence"
  | "source_diversity"
  | "source_url_coverage"
  | "human_review_coverage";

export type EvidenceReadiness = {
  level: EvidenceReadinessLevel;
  evidence_count: number;
  source_count: number;
  safe_url_count: number;
  reviewed_count: number;
  source_url_coverage: number;
  human_review_coverage: number;
  checks: Record<EvidenceReadinessCheck, boolean>;
  passed_checks: EvidenceReadinessCheck[];
  gaps: string[];
};

export type OpportunityReviewUpdate = {
  review_state: ReviewState;
  review_note: string | null;
};

export type EvidenceReviewCreate = {
  item_id: string;
  label: EvidenceReviewLabel;
  user_note: string | null;
};

export type LabelOut = {
  id: string;
  item_id: string;
  label: string;
  user_note: string | null;
  created_at: string;
};

export type EvaluationLabelCounts = Record<EvidenceReviewLabel, number>;

export type EvaluationSlice = {
  total_items: number;
  reviewed_items: number;
  review_coverage: number;
  label_counts: EvaluationLabelCounts;
  precision_on_reviewed_positives: number | null;
};

export type Evaluation = {
  total_reviewable_items: number;
  reviewed_items: number;
  review_coverage: number;
  label_counts: EvaluationLabelCounts;
  unrecognized_latest_labels: number;
  precision_on_reviewed_positives: number | null;
  by_source: Record<string, EvaluationSlice>;
  by_signal_type: Record<string, EvaluationSlice>;
  selection_bias_warning: string;
};

export type EvidenceItem = {
  id: string;
  source: string;
  external_id: string;
  url: string;
  title: string;
  body: string;
  score: number | null;
  comments_count: number | null;
  created_at: string;
  tags: string[];
  signal_type: string | null;
  pain_score: number | null;
  task_concreteness_score: number | null;
  buying_intent_score: number | null;
  evidence_spans: string[];
  review_label: EvidenceReviewLabel | null;
  review_note: string | null;
  reviewed_at: string | null;
  review_version: number | null;
  review_history_count: number;
  agent_review_label: EvidenceReviewLabel | null;
  agent_reviewed_at: string | null;
  agent_review_history_count: number;
  agent_review_version: number | null;
  agent_session_id: string | null;
};

export type ScoreBreakdown = {
  frequency?: number;
  recency?: number;
  pain_intensity?: number;
  task_concreteness?: number;
  buying_intent?: number;
  feasibility?: number;
  competition_penalty?: number;
  opportunity_score?: number;
  explanation?: string;
  score_formula?: string;
  rank_drivers?: string[];
  common_phrases?: string[];
  [key: string]: number | string | string[] | undefined;
};

export type Opportunity = {
  id: string;
  thread_id?: string | null;
  run_id?: string | null;
  scan_id?: string | null;
  cluster_id: string;
  evidence_hash?: string | null;
  content_hash?: string | null;
  match_method?: string | null;
  match_confidence?: number | null;
  match_margin?: number | null;
  centroid_similarity?: number | null;
  evidence_jaccard?: number | null;
  title_jaccard?: number | null;
  embedding_model?: string | null;
  embedding_backend?: string | null;
  detached?: boolean;
  detached_from_thread_id?: string | null;
  title: string;
  problem_statement: string;
  target_user: string;
  current_workaround: string;
  suggested_mvp: string;
  why_now: string;
  feasibility_score: number;
  opportunity_score: number;
  competition_notes: string;
  scoring_breakdown_json: ScoreBreakdown;
  generated_prompt: string;
  review_state: ReviewState;
  review_note: string | null;
  decision_updated_at: string | null;
  created_at: string;
  updated_at: string;
  evidence_items: EvidenceItem[];
  signal_count: number;
  top_source: string;
  evidence_readiness: EvidenceReadiness;
};

export type Source = {
  id: string;
  name: string;
  type: string;
  config_json: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
};

export type Integration = {
  id: string;
  name: string;
  kind: string;
  status: string;
  credential_state: string;
  public_scan_enabled: boolean;
  operator_token_required: boolean;
  required_env: string[];
  optional_env: string[];
  rate_limit_note: string;
  privacy_note: string;
  next_step: string;
  last_scan_status: string | null;
  last_scan_at: string | null;
};

export type IntegrationTest = {
  id: string;
  status: string;
  detail: string;
  items_found: number;
};

export type LocalWorkspace = {
  id: number;
  owner_name: string;
  workspace_goal: string;
  default_source_type: string;
  default_query: string;
  default_limit: number;
  default_cadence: string;
  default_schedule_interval_hours: number | null;
  configured: boolean;
  created_at: string;
  updated_at: string;
};

export type LocalWorkspaceUpdate = {
  owner_name: string;
  workspace_goal: string;
  default_source_type: string;
  default_query: string;
  default_limit: number;
  default_cadence: string;
  default_schedule_interval_hours?: number | null;
};

export type Readiness = {
  status: string;
  blockers: string[];
  warnings: string[];
  checks: {
    projects?: number;
    opportunities?: number;
    due_projects?: number;
    local_workspace_configured?: boolean;
    ready_sources?: string[];
    codex_task_packs?: boolean;
    operator_scan_token_configured?: boolean;
    public_scan_sources?: string[];
    public_scan_sources_configured?: boolean;
    [key: string]: unknown;
  };
};

export type ResearchProject = {
  id: string;
  name: string;
  description: string | null;
  source_type: string;
  source_id?: string | null;
  query: string;
  limit: number;
  cadence: string;
  schedule_interval_hours: number | null;
  labels: string[];
  enabled: boolean;
  last_scan_id: string | null;
  last_scan_status: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  version?: number;
  created_at: string;
  updated_at: string;
};

export type ResearchRun = {
  id: string;
  project_id: string;
  scan_id: string;
  sequence: number | null;
  source_type: string | null;
  source_origin: string | null;
  query: string | null;
  requested_limit: number | null;
  lineage_status: "complete" | "incomplete" | "untracked";
  scan_status: string;
  started_at: string;
  finished_at: string | null;
  items_found: number;
  items_saved: number;
  signals_detected: number;
  clusters_created: number;
  opportunities_created: number;
  created_at: string;
};

export type RunDeltaCounts = {
  new: number;
  seen_before: number;
  updated: number;
  unchanged: number;
  not_observed_this_run: number;
};

export type RunDelta = {
  project_id: string;
  run_id: string;
  scan_id: string;
  sequence: number;
  previous_run_id: string | null;
  evidence_changes: RunDeltaCounts;
  signal_changes: RunDeltaCounts;
  generated_snapshots: { clusters: number; opportunities: number };
  opportunity_changes: {
    new: number;
    updated: number;
    unchanged: number;
    not_observed_this_run: number;
  } | null;
  warnings: string[];
};

export type OpportunityDecisionEvent = {
  id: string;
  thread_id: string;
  event_type: string;
  actor_type: string;
  agent_session_id: string | null;
  snapshot_id: string | null;
  related_thread_id: string | null;
  previous_state: ReviewState | null;
  next_state: ReviewState | null;
  previous_note: string | null;
  next_note: string | null;
  details_json: Record<string, unknown>;
  created_at: string;
};

export type OpportunityThreadSummary = {
  id: string;
  project_id: string | null;
  lineage_status: "complete" | "untracked";
  review_state: ReviewState;
  review_note: string | null;
  decision_updated_at: string | null;
  version: number;
  snapshot_count: number;
  current_snapshot: Opportunity | null;
  created_at: string;
  updated_at: string;
};

export type OpportunityThread = OpportunityThreadSummary & {
  snapshots: Opportunity[];
  decision_history: OpportunityDecisionEvent[];
};

export type DetachSnapshotResult = {
  source_thread: OpportunityThread;
  new_thread: OpportunityThread;
};

export type EvidenceSearchObservation = {
  source: string;
  source_url: string;
  scan_id: string;
  run_id: string | null;
  project_id: string | null;
};

export type EvidenceSearchHit = {
  id: string;
  source: string;
  title: string;
  excerpt: string;
  source_url: string;
  match_score: number;
  signal_type: string | null;
  review_label: EvidenceReviewLabel | null;
  created_at: string;
  untrusted_evidence: true;
  provenance: {
    evidence_hash: string;
    scan_ids: string[];
    run_ids: string[];
    project_ids: string[];
    observations: EvidenceSearchObservation[];
  };
};

export type OpportunityThreadSearchHit = {
  id: string;
  project_id: string | null;
  title: string;
  summary: string;
  match_score: number;
  matched_evidence_ids: string[];
  matched_evidence_count: number;
  review_state: ReviewState;
  lineage_status: "complete" | "untracked";
  evidence_readiness: EvidenceReadiness;
  provenance: {
    snapshot_id: string;
    run_id: string | null;
    scan_id: string | null;
    evidence_hash: string;
    content_hash: string;
    match_method: string;
    match_confidence: number | null;
  };
};

export type SemanticSearch = {
  evidence_hits: EvidenceSearchHit[];
  opportunity_threads: OpportunityThreadSearchHit[];
};

export type BuildPacketArtifact = {
  path: string;
  content: string;
  byte_count: number;
  sha256: string;
};

export type BuildPacketSummary = {
  id: string;
  project_id: string | null;
  run_id: string | null;
  thread_id: string;
  snapshot_id: string;
  lineage_status: "complete" | "untracked";
  generation_mode: "deterministic" | "configured_ai";
  schema_version: string;
  tasksignal_version: string;
  template_version: string;
  generated_at: string;
  enhancement_status: "not_requested" | "generated" | "fallback";
  enhancement_provider: string | null;
  enhancement_model: string | null;
  artifact_count: number;
  total_bytes: number;
  manifest_sha256: string;
  created_at: string;
};

export type BuildPacket = Omit<
  BuildPacketSummary,
  "artifact_count" | "total_bytes"
> & {
  enhancement_template_version: string | null;
  artifacts: BuildPacketArtifact[];
  manifest: Record<string, unknown>;
};

export type BuildPacketVerification = {
  packet_id: string;
  valid: boolean;
  errors: string[];
  missing_files: string[];
  unexpected_files: string[];
  mismatched_files: string[];
};

export type SourceAuthorization = {
  source_id: string;
  source_type: string;
  origin: string | null;
  host: string | null;
  port: number | null;
  authorized: boolean;
  authorized_at: string | null;
  terms_confirmed_at: string | null;
};

export type SourceRuntimeState = {
  source_id: string;
  origin: string | null;
  readiness:
    | "ready"
    | "disabled"
    | "terms_required"
    | "retry_later"
    | "failed"
    | "never_run";
  can_run: boolean;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_failure_code: string | null;
  last_failure_message: string | null;
  last_http_status: number | null;
  retry_after_at: string | null;
};

export type AgentSession = {
  id: string;
  process_instance_id: string;
  client_name: string;
  client_version: string | null;
  transport: "stdio";
  status: "pending" | "approved" | "revoked" | "expired" | "exited";
  effective_status: "pending" | "approved" | "revoked" | "expired" | "exited";
  requested_capabilities: string[];
  approved_capabilities: string[];
  approval_source: "ui" | "interactive_tty" | null;
  approved_at: string | null;
  last_heartbeat_at: string;
  expires_at: string;
  revoked_at: string | null;
  expired_at: string | null;
  exited_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

export type AgentAction = {
  id: string;
  session_id: string;
  operation_id: string;
  correlation_id: string;
  event_sequence: number;
  event_status:
    | "reserved"
    | "succeeded"
    | "failed"
    | "conflict"
    | "replayed"
    | "denied";
  capability: string;
  tool_name: string;
  target_type: string | null;
  target_id: string | null;
  request_summary: Record<string, unknown>;
  result_summary: Record<string, unknown> | null;
  error_code: string | null;
  created_at: string;
};

export type ResearchProjectCreate = {
  name: string;
  description?: string | null;
  source_type: string;
  source_id?: string | null;
  query: string;
  limit: number;
  cadence: string;
  schedule_interval_hours?: number | null;
  labels: string[];
  enabled: boolean;
};

export type DueRun = {
  ran: number;
  skipped: number;
  scans: Scan[];
};

export type Scan = {
  id: string;
  source_id: string | null;
  source_type: string | null;
  source_name: string | null;
  status: string;
  query: string | null;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  items_found: number;
  items_saved: number;
  signals_detected: number;
  clusters_created: number;
  opportunities_created: number;
  outcome_message: string | null;
};

export type ScanCreate = {
  source: string;
  query: string;
  limit: number;
};

export type TaskPack = {
  opportunity_id: string;
  title: string;
  problem: string;
  suggested_mvp: string;
  codex_prompt: string;
  markdown: string;
  evidence_urls: string[];
  acceptance_criteria: string[];
  privacy_constraints: string[];
  review_state: ReviewState;
  evidence_readiness: EvidenceReadiness;
};

export type Enhancement = {
  provider: string;
  model: string;
  enhanced_prompt: string;
  applied: boolean;
};
