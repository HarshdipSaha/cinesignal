// API contract types for CineSignal backend (see build spec / api/main.py contract).
// The backend is owned by another process — these types are a best-effort mirror
// of the documented contract, kept deliberately loose (optional fields, index
// signatures) so the UI degrades gracefully if the real shape drifts slightly.

export type EntityType = "film" | "series" | "person" | "franchise" | string;

export interface EntitySummary {
  wikidata_id: string;
  label: string;
  entity_type?: EntityType;
  year?: number | null;
  tconst?: string | null;
  nconst?: string | null;
  genres?: string[] | null;
  release_date?: string | null;
  // Resolve endpoints sometimes attach a match-quality score to candidates.
  score?: number | null;
}

export interface ResolveResponse {
  query?: string;
  best_match?: EntitySummary | null;
  candidates?: EntitySummary[];
}

export type PlaybookId = "title_pulse" | "campaign_impact" | "launch_window";

export interface PlaybookRunRequest {
  entity_id: string;
  params: Record<string, unknown>;
}

// ---- SSE stream event shapes ----

export interface StageEvent {
  type: "stage";
  stage?: string;
  message?: string;
  entity?: string;
  headline?: string;
  verdict?: string;
  [key: string]: unknown;
}

export interface StepEvent {
  type: "step";
  step_id?: string;
  title?: string;
  query_id?: string;
  row_count?: number;
  elapsed_ms?: number;
  error?: string | null;
  [key: string]: unknown;
}

export interface ErrorEvent {
  type: "error";
  message?: string;
  [key: string]: unknown;
}

export interface DoneEvent {
  type: "done";
  memo_id?: string;
  validated?: boolean;
  [key: string]: unknown;
}

export type PlaybookStreamEvent = StageEvent | StepEvent | ErrorEvent | DoneEvent;

// ---- Memo ----

export type Verdict =
  | "BREAKOUT"
  | "IN_LINE"
  | "UNDERPERFORMED"
  | "RISING"
  | "DECLINING"
  | "STABLE"
  | "RANKED"
  | "INSUFFICIENT_DATA"
  | string;

export interface MemoSection {
  heading: string;
  body: string;
}

export interface MemoFinding {
  key: string;
  label: string;
  value: number | string | null;
  unit?: string | null;
  query_id?: string | null;
  extra?: Record<string, unknown> | null;
}

export interface SpilloverEntity {
  wikidata_id: string;
  label: string;
  pct_lift: number;
}

export interface CampaignImpactChartData {
  event_date?: string;
  dates?: string[];
  actual?: number[];
  counterfactual?: number[];
  spillover?: SpilloverEntity[];
}

export interface AnomalyDay {
  date: string;
  delta_views?: number;
  z_score?: number;
}

export interface MonthlyPercentile {
  month: string;
  percentile: number;
  views?: number;
}

export interface TitlePulseChartData {
  dates?: string[];
  views?: number[];
  anomaly_days?: AnomalyDay[];
  monthly_percentile?: MonthlyPercentile[] | null;
}

export interface LaunchWeekend {
  weekend: string;
  competitor_count?: number;
  competitors?: string[];
  attention_mass?: number;
  seasonal_index?: number;
  combined_score?: number;
}

export interface LaunchWindowChartData {
  quarter_start?: string;
  quarter_end?: string;
  weekends?: LaunchWeekend[];
  top3?: LaunchWeekend[];
}

export type ChartData =
  | CampaignImpactChartData
  | TitlePulseChartData
  | LaunchWindowChartData
  | Record<string, unknown>
  | null
  | undefined;

export interface Memo {
  memo_id: string;
  playbook_id: string;
  playbook_version?: number;
  entity: EntitySummary;
  params?: Record<string, unknown>;
  verdict: Verdict;
  headline: string;
  sections: MemoSection[];
  findings: MemoFinding[];
  chart_data: ChartData;
  query_ids: string[];
  validated?: boolean;
  validator_notes?: string;
}

// ---- Evidence ----

export interface EvidenceResponse {
  query_id: string;
  sql: string;
  params?: Record<string, unknown>;
  rows: Record<string, unknown>[];
  row_count: number;
  rows_scanned?: number;
  elapsed_ms?: number;
  created_at?: string;
}

// ---- Explore ----

export interface ExploreSeriesPoint {
  date: string;
  views: number;
}

export interface ExploreResponse {
  entity: EntitySummary;
  series: ExploreSeriesPoint[];
}
