/**
 * Backend client and shared types.
 *
 * Types mirror the Pydantic contracts in backend/app/schemas. They are hand
 * written for now; generating them from the FastAPI OpenAPI schema is the
 * intended follow-up so they cannot drift.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "interrupted";

export type EvidenceStrength = "strong" | "moderate" | "weak" | "anecdotal";
export type ClaimKind = "fact" | "estimate" | "assumption";
export type Provenance = "sourced" | "calculated" | "assumed";

export interface Claim {
  id: string;
  text: string;
  kind: ClaimKind;
  evidence_strength: EvidenceStrength;
  confidence: number;
  source_url: string | null;
  source_title: string | null;
  published_date: string | null;
}

export interface CategoryScore {
  category: string;
  weight: number;
  proposed_rating: number;
  effective_rating: number;
  points: number;
  max_points: number;
  best_evidence: EvidenceStrength | null;
  supporting_claims: number;
  evidence_coverage: number;
  adjustments: string[];
}

export interface OpportunityScore {
  total: number;
  band: "strong" | "promising" | "weak" | "high_risk";
  band_label: string;
  categories: CategoryScore[];
  penalties: string[];
  penalty_points: number;
  disclaimer: string;
}

// --- Report contracts (mirror backend/app/schemas/contracts.py) -----------

export interface Number_ {
  id: string;
  label: string;
  value: number;
  unit: string;
  provenance: Provenance;
  formula: string | null;
  source_claim_id: string | null;
  rationale: string | null;
}

export interface StartupHypothesis {
  problem_statement: string;
  target_segment: string;
  proposed_solution: string;
  value_hypothesis: string;
  riskiest_assumptions: string[];
  research_questions: string[];
  missing_information: string[];
}

export interface Competitor {
  name: string;
  target_user: string;
  pricing: string | null;
  strengths: string[];
  weaknesses: string[];
  opportunity: string | null;
  source_url: string | null;
}

export interface CompetitorSet {
  direct: Competitor[];
  indirect: Competitor[];
  gaps: string[];
  evidence: Claim[];
}

export interface Persona {
  name: string;
  description: string;
  jobs_to_be_done: string[];
  pains: string[];
  current_alternatives: string[];
  willingness_to_pay_hypothesis: string | null;
  is_early_adopter: boolean;
  validation_status: string;
}

export interface PersonaSet {
  personas: Persona[];
  interview_questions: string[];
  evidence: Claim[];
}

export interface MarketFindings {
  problem_evidence: Claim[];
  demand_signals: Claim[];
  trends: Claim[];
  market_size_notes: string | null;
  unknowns: string[];
}

export interface Scenario {
  name: string;
  assumptions: Number_[];
  monthly_revenue: Number_;
  monthly_costs: Number_;
  break_even_customers: Number_;
  notes: string | null;
}

export interface FinancialScenarios {
  conservative: Scenario;
  realistic: Scenario;
  optimistic: Scenario;
  pricing_rationale: string;
}

export interface Contradiction {
  description: string;
  agents_involved: string[];
  severity: string;
}

export interface CriticVerdict {
  summary: string;
  contradictions: Contradiction[];
  unsupported_claims: string[];
  outdated_sources: string[];
  unsound_categories: string[];
  must_validate_manually: string[];
  verdict: string;
}

export interface ValidationStep {
  day: number;
  action: string;
  success_signal: string;
}

export interface OpportunityReport {
  executive_summary: string;
  hypothesis: StartupHypothesis;
  problem_analysis: string;
  segments: PersonaSet;
  market_evidence: MarketFindings;
  competitors: CompetitorSet;
  differentiation: string[];
  revenue_model_analysis: string;
  financials: FinancialScenarios;
  key_assumptions: string[];
  major_risks: string[];
  critic_verdict: CriticVerdict;
  validation_plan: ValidationStep[];
  interview_questions: string[];
}

export interface RunSummary {
  id: string;
  status: RunStatus;
  score_total: number | null;
  score_band: string | null;
  idea: string;
  created_at: string;
  error: string | null;
}

export interface ProgressEvent {
  seq: number;
  node: string;
  phase: "started" | "completed" | "failed" | "attribution_failed";
  payload: Record<string, unknown> | null;
}

export interface IdeaSubmission {
  idea: string;
  target_customer: string;
  country: string;
  industry: string;
  revenue_model: string;
  monthly_budget_eur?: number | null;
  founder_skills?: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  createRun: (submission: IdeaSubmission) =>
    request<{ id: string; status: RunStatus }>("/api/runs", {
      method: "POST",
      body: JSON.stringify(submission),
    }),

  listRuns: () => request<RunSummary[]>("/api/runs"),

  getRun: (id: string) =>
    request<{
      id: string;
      status: RunStatus;
      score_total: number | null;
      score_band: string | null;
      usage: Record<string, unknown> | null;
      error: string | null;
    }>(`/api/runs/${id}`),

  getReport: (id: string) =>
    request<{
      content: Record<string, unknown>;
      score: OpportunityScore;
      markdown: string;
    }>(`/api/runs/${id}/report`),

  streamUrl: (id: string) => `${API_BASE}/api/runs/${id}/stream`,
};

/** Stage order for the progress UI. The three research nodes run concurrently. */
export const STAGES: { node: string; label: string; parallel?: boolean }[] = [
  { node: "manager", label: "Structuring the hypothesis" },
  { node: "market_search", label: "Researching the market", parallel: true },
  { node: "competitor_search", label: "Analysing competitors", parallel: true },
  { node: "persona_search", label: "Building customer segments", parallel: true },
  { node: "financial", label: "Modelling financial scenarios" },
  { node: "critic", label: "Challenging the findings" },
  { node: "reporter", label: "Assembling the report" },
];

/**
 * Score bands are an ordinal severity scale, so they use the reserved status
 * palette rather than series colours. Status colour never travels alone —
 * every use pairs it with the band label and a glyph.
 */
export interface BandStyle {
  text: string;
  bg: string;
  border: string;
  glyph: string;
  short: string;
}

export const BANDS: Record<string, BandStyle> = {
  strong: {
    text: "text-good",
    bg: "bg-good/10",
    border: "border-good/30",
    glyph: "▲",
    short: "Strong",
  },
  promising: {
    text: "text-warning",
    bg: "bg-warning/10",
    border: "border-warning/30",
    glyph: "◆",
    short: "Promising",
  },
  weak: {
    text: "text-serious",
    bg: "bg-serious/10",
    border: "border-serious/30",
    glyph: "▼",
    short: "Weak",
  },
  high_risk: {
    text: "text-critical",
    bg: "bg-critical/10",
    border: "border-critical/30",
    glyph: "■",
    short: "High risk",
  },
};

export const UNKNOWN_BAND: BandStyle = {
  text: "text-ink-muted",
  bg: "bg-sunken",
  border: "border-hairline",
  glyph: "·",
  short: "Pending",
};

export function bandStyle(band: string | null | undefined): BandStyle {
  return (band && BANDS[band]) || UNKNOWN_BAND;
}

/** Compact currency for axis ticks and stat tiles. */
export function formatMoney(value: number, unit = "EUR"): string {
  const symbol = unit.toUpperCase() === "EUR" ? "€" : unit.toUpperCase() === "USD" ? "$" : "";
  const abs = Math.abs(value);
  const compact =
    abs >= 1_000_000
      ? `${(value / 1_000_000).toFixed(1)}M`
      : abs >= 1_000
        ? `${(value / 1_000).toFixed(abs >= 10_000 ? 0 : 1)}K`
        : value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return symbol ? `${symbol}${compact}` : `${compact} ${unit}`;
}
