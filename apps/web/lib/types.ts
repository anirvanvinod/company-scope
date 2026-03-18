/**
 * TypeScript interfaces for the CompanyScope Phase 7A API surface.
 *
 * These mirror the Pydantic schemas in apps/api/app/schemas/.
 * All date fields are ISO 8601 strings (the API uses mode="json" on model_dump).
 * Decimal fields arrive as strings (Pydantic JSON serialisation).
 */

// ---------------------------------------------------------------------------
// Envelope
// ---------------------------------------------------------------------------

export interface ApiMeta {
  request_id: string;
  generated_at: string;
}

export interface ApiListMeta extends ApiMeta {
  pagination: {
    next_cursor: string | null;
    limit: number;
  };
}

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export interface SearchResultItem {
  company_number: string;
  company_name: string;
  company_status: string | null;
  company_type: string | null;
  date_of_creation: string | null;
  registered_office_address_snippet: string | null;
  sic_codes: string[];
  match_type: "exact_number" | "name";
}

// ---------------------------------------------------------------------------
// Company aggregate
// ---------------------------------------------------------------------------

export interface CompanyCore {
  company_number: string;
  company_name: string;
  company_status: string | null;
  company_type: string | null;
  subtype: string | null;
  jurisdiction: string | null;
  date_of_creation: string | null;
  cessation_date: string | null;
  has_insolvency_history: boolean | null;
  has_charges: boolean | null;
  sic_codes: string[];
  registered_office_address: Record<string, string> | null;
}

export interface CompanyOverview {
  accounts_next_due: string | null;
  accounts_overdue: boolean | null;
  confirmation_statement_next_due: string | null;
  confirmation_statement_overdue: boolean | null;
}

export type ConfidenceBand = "high" | "medium" | "low" | "unavailable";

export interface FinancialSummary {
  latest_period_end: string | null;
  period_start: string | null;
  accounts_type: string | null;
  currency_code: string | null;
  /** Decimal serialised as string */
  confidence: string | null;
  confidence_band: ConfidenceBand;
  revenue: string | null;
  net_assets_liabilities: string | null;
  profit_loss_after_tax: string | null;
  average_number_of_employees: string | null;
}

export type SignalSeverity = "high" | "medium" | "low" | "info";

export interface ActiveSignalSummary {
  signal_code: string;
  signal_name: string;
  category: string;
  severity: SignalSeverity;
  explanation: string;
}

export interface NarrativeParagraph {
  topic: string;
  text: string;
  confidence_note: string | null;
}

export interface KeyObservation {
  observation: string;
  severity: string;
  evidence_ref: string;
}

export interface AiNarrativeSummary {
  summary_short: string;
  narrative_paragraphs: NarrativeParagraph[];
  key_observations: KeyObservation[];
  data_quality_note: string | null;
  caveats: string[];
  source: "ai" | "template";
}

export interface Freshness {
  snapshot_generated_at: string | null;
  source_last_checked_at: string | null;
  freshness_status: string;
  snapshot_status: "current" | "not_built";
  methodology_version: string | null;
}

export interface CompanyAggregate {
  company: CompanyCore;
  overview: CompanyOverview;
  financial_summary: FinancialSummary | null;
  active_signals: ActiveSignalSummary[];
  ai_summary: AiNarrativeSummary | null;
  freshness: Freshness;
}
