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

export type EvidenceItem = {
  id: string;
  source: string;
  url: string;
  title: string;
  body: string;
  signal_type: string;
  pain_score: number;
  task_concreteness_score: number;
  buying_intent_score: number;
  evidence_spans: string[];
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
  created_at: string;
  updated_at: string;
  evidence_items: EvidenceItem[];
  signal_count: number;
  top_source: string;
};

export type Source = {
  id: string;
  name: string;
  type: string;
  config_json: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
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
};

export type ScanCreate = {
  source: string;
  query: string;
  limit: number;
};
