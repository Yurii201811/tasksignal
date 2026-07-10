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
  review_history_count: number;
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
  cluster_id: string;
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
  created_at: string;
  updated_at: string;
};

export type ResearchProjectCreate = {
  name: string;
  description?: string | null;
  source_type: string;
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
