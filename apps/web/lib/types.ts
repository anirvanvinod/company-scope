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

// ---------------------------------------------------------------------------
// Financials
// ---------------------------------------------------------------------------

export interface FactDetail {
  /** Decimal serialised as string; null means not extractable */
  value: string | null;
  unit: string | null;
  /** Decimal serialised as string */
  confidence: string | null;
  confidence_band: ConfidenceBand;
  /** Verbatim label from the source document */
  raw_label: string | null;
  extraction_method: string | null;
  is_derived: boolean;
}

export interface PeriodFacts {
  period_id: string;
  period_end: string;
  period_start: string | null;
  accounts_type: string | null;
  currency_code: string | null;
  extraction_confidence: string | null;
  confidence_band: ConfidenceBand;
  /** Keyed by canonical fact name (e.g. "revenue", "net_assets_liabilities") */
  facts: Record<string, FactDetail>;
}

export interface MetricDetail {
  value: string | null;
  unit: string;
  confidence: string | null;
  confidence_band: ConfidenceBand;
  warnings: string[];
}

export interface SeriesPoint {
  period_end: string;
  value: string | null;
  confidence_band: ConfidenceBand;
}

export interface FinancialsDataQuality {
  periods_available?: number;
  primary_period_facts_available?: number;
  primary_period_confidence_band?: string;
  /** Set when no financial data is available at all */
  message?: string;
}

export interface FinancialsResponse {
  periods: PeriodFacts[];
  derived_metrics: Record<string, MetricDetail>;
  series: Record<string, SeriesPoint[]>;
  data_quality: FinancialsDataQuality;
}

// ---------------------------------------------------------------------------
// Filings
// ---------------------------------------------------------------------------

export interface FilingItem {
  transaction_id: string;
  category: string | null;
  type: string | null;
  description: string | null;
  action_date: string | null;
  date_filed: string | null;
  pages: number | null;
  paper_filed: boolean | null;
  has_document: boolean;
  parse_status: string | null;
  source_links: Record<string, string> | null;
}

// ---------------------------------------------------------------------------
// Officers
// ---------------------------------------------------------------------------

export interface OfficerItem {
  name: string;
  role: string | null;
  nationality: string | null;
  occupation: string | null;
  country_of_residence: string | null;
  appointed_on: string | null;
  resigned_on: string | null;
  is_current: boolean;
  date_of_birth_month: number | null;
  date_of_birth_year: number | null;
}

// ---------------------------------------------------------------------------
// PSC (persons with significant control)
// ---------------------------------------------------------------------------

export interface PscItem {
  name: string | null;
  kind: string | null;
  natures_of_control: string[];
  notified_on: string | null;
  ceased_on: string | null;
  nationality: string | null;
  country_of_residence: string | null;
  is_current: boolean;
  date_of_birth_month: number | null;
  date_of_birth_year: number | null;
}

// ---------------------------------------------------------------------------
// Auth / user
// ---------------------------------------------------------------------------

export interface UserProfile {
  id: string;
  email: string;
  display_name: string | null;
  auth_provider: string;
}

export interface WatchlistOut {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  item_count: number;
  created_at: string | null;
}

export interface WatchlistItemOut {
  company_number: string;
  company_name: string;
  company_status: string | null;
  monitoring_status: string;
  added_at: string;
}

// ---------------------------------------------------------------------------
// Charges
// ---------------------------------------------------------------------------

export interface ChargeItem {
  charge_id: string;
  status: string | null;
  delivered_on: string | null;
  created_on: string | null;
  resolved_on: string | null;
  persons_entitled: Array<{ name: string }> | null;
  particulars: Record<string, unknown> | null;
  source_last_checked_at: string | null;
}
