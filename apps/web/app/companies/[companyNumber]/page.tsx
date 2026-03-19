/**
 * Company overview page.
 *
 * Information hierarchy (docs/11-ui-ux-principles.md §Hierarchy principles):
 *   1. Active signals (alert strip)
 *   2. Key financial facts + confidence
 *   3. AI/template narrative + observations
 *   4. Compliance overview + freshness
 *
 * Company identity and tab nav are now rendered by layout.tsx.
 *
 * Data strategy:
 *   - getCompany() returns the snapshot-first aggregate from GET /api/v1/companies/{number}
 *   - Next.js deduplicates the fetch: layout.tsx and page.tsx share one request
 *   - If snapshot_status === "not_built" we show identity data + a pending notice
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { getCompany, getWatchlists, getWatchlistItems } from "@/lib/api";
import { getServerSession, getAuthHeader } from "@/lib/auth";
import {
  cn,
  formatDate,
  formatCurrency,
  formatAccountsType,
  formatNumber,
  formatCompanyType,
} from "@/lib/utils";
import { ConfidencePip } from "@/components/ui/ConfidencePip";
import { FreshnessTag } from "@/components/ui/FreshnessTag";
import { SignalCard } from "@/components/ui/SignalCard";
import { NullState } from "@/components/ui/NullState";
import { WatchlistButton } from "@/components/company/WatchlistButton";
import type {
  CompanyAggregate,
  FinancialSummary,
  AiNarrativeSummary,
  Freshness,
  CompanyOverview,
} from "@/lib/types";

interface PageProps {
  params: Promise<{ companyNumber: string }>;
}

// ---------------------------------------------------------------------------
// Metadata
// ---------------------------------------------------------------------------

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { companyNumber } = await params;
  const { data } = await getCompany(companyNumber);
  if (!data) return { title: `${companyNumber} — Not found` };
  return {
    title: `${data.company.company_name} (${companyNumber})`,
    description: [
      data.company.company_name,
      formatCompanyType(data.company.company_type),
      data.company.company_status === "active" ? "Active" : null,
    ]
      .filter(Boolean)
      .join(" · "),
  };
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default async function CompanyOverviewPage({ params }: PageProps) {
  const { companyNumber } = await params;
  const { data, error, isNotFound } = await getCompany(companyNumber);

  if (isNotFound) notFound();

  if (!data) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <NullState
          reason={`Could not load company data${error ? `: ${error}` : ""}. Please try again.`}
        />
      </main>
    );
  }

  const { company, overview, financial_summary, active_signals, ai_summary, freshness } =
    data as CompanyAggregate;

  const hasSignals = active_signals.length > 0;
  const snapshotBuilt = freshness.snapshot_status === "current";

  // Watchlist state — computed server-side so WatchlistButton renders with correct initial state
  const user = await getServerSession();
  const authHeaders = await getAuthHeader();
  let isWatched = false;
  let defaultWatchlistId: string | null = null;

  if (user) {
    const { data: wlData } = await getWatchlists(authHeaders as Record<string, string>);
    const lists = wlData ?? [];
    const defaultList = lists.find((w) => w.is_default) ?? lists[0] ?? null;
    defaultWatchlistId = defaultList?.id ?? null;

    if (defaultList) {
      // Fetch items for the default watchlist to determine watched state
      const { data: wlDetail } = await getWatchlistItems(
        defaultList.id,
        authHeaders as Record<string, string>,
      );
      isWatched =
        (wlDetail?.items ?? []).some(
          (item) => item.company_number === companyNumber,
        ) ?? false;
    }
  }

  return (
    <main>
      {/* ---------------------------------------------------------------- */}
      {/* Watchlist button + signal strip                                  */}
      {/* ---------------------------------------------------------------- */}
      <div className="border-b border-stone-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <p className="text-xs text-stone-400">
              {hasSignals
                ? `${active_signals.length} active signal${active_signals.length !== 1 ? "s" : ""}`
                : "No active signals"}
            </p>
            <WatchlistButton
              companyNumber={companyNumber}
              isWatched={isWatched}
              watchlistId={defaultWatchlistId}
              unauthenticated={!user}
            />
          </div>
        </div>
      </div>

      {hasSignals && (
        <section
          className="border-b border-stone-200 bg-white"
          aria-label="Active risk signals"
        >
          <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
            <div className="flex flex-wrap gap-2">
              {active_signals.map((sig) => (
                <SignalCard key={sig.signal_code} signal={sig} compact />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Main content                                                     */}
      {/* ---------------------------------------------------------------- */}
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* ---- Left / main column ------------------------------------ */}
          <div className="space-y-6 lg:col-span-2">
            {/* Snapshot pending notice */}
            {!snapshotBuilt && (
              <div className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-4">
                <p className="text-sm text-stone-500">
                  <span className="font-medium text-stone-700">
                    Analysis pending.
                  </span>{" "}
                  Financial analysis and risk signals are being prepared. Company
                  identity and compliance data are available above.
                </p>
              </div>
            )}

            {/* Financial snapshot */}
            <FinancialSnapshotCard
              summary={financial_summary}
              snapshotBuilt={snapshotBuilt}
            />

            {/* AI / template narrative */}
            {snapshotBuilt && (
              <NarrativeCard aiSummary={ai_summary} />
            )}
          </div>

          {/* ---- Right / sidebar column -------------------------------- */}
          <div className="space-y-6">
            {/* Compliance overview */}
            <ComplianceCard overview={overview} />

            {/* Freshness */}
            <FreshnessCard freshness={freshness} />

            {/* SIC codes */}
            {company.sic_codes.length > 0 && (
              <SicCard codes={company.sic_codes} />
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

// ---- Financial snapshot card -------------------------------------------

function FinancialSnapshotCard({
  summary,
  snapshotBuilt,
}: {
  summary: FinancialSummary | null;
  snapshotBuilt: boolean;
}) {
  return (
    <section aria-labelledby="financial-heading">
      <div className="rounded-lg border border-stone-200 bg-white">
        <div className="flex items-center justify-between border-b border-stone-100 px-5 py-4">
          <h2
            id="financial-heading"
            className="text-sm font-semibold text-stone-900"
          >
            Financial snapshot
          </h2>
          {summary && (
            <ConfidencePip band={summary.confidence_band} label />
          )}
        </div>

        <div className="px-5 py-4">
          {!snapshotBuilt ? (
            <p className="text-sm text-stone-400 italic">
              Financial data will appear once analysis is complete.
            </p>
          ) : !summary ? (
            <NullState
              reason="No financial data extracted yet. Financial analysis requires at least one set of filed accounts to have been parsed."
              className="border-0 bg-transparent p-0 text-left"
            />
          ) : (
            <FinancialSummaryContent summary={summary} />
          )}
        </div>
      </div>
    </section>
  );
}

function FinancialSummaryContent({ summary }: { summary: FinancialSummary }) {
  const currency = summary.currency_code;
  const periodRange =
    summary.period_start && summary.latest_period_end
      ? `${formatDate(summary.period_start)} – ${formatDate(summary.latest_period_end)}`
      : summary.latest_period_end
        ? `Year ended ${formatDate(summary.latest_period_end)}`
        : null;

  return (
    <div>
      {/* Period meta */}
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-stone-400">
        {periodRange && <span>{periodRange}</span>}
        {summary.accounts_type && (
          <span>{formatAccountsType(summary.accounts_type) ?? summary.accounts_type}</span>
        )}
        {currency && <span>{currency}</span>}
      </div>

      {/* Key metrics */}
      <dl className="grid grid-cols-2 gap-4">
        <MetricItem
          label="Revenue"
          value={formatCurrency(summary.revenue, currency)}
        />
        <MetricItem
          label="Net assets"
          value={formatCurrency(summary.net_assets_liabilities, currency)}
        />
        <MetricItem
          label="Profit after tax"
          value={formatCurrency(summary.profit_loss_after_tax, currency)}
        />
        <MetricItem
          label="Employees"
          value={
            summary.average_number_of_employees
              ? formatNumber(summary.average_number_of_employees)
              : null
          }
        />
      </dl>

      <p className="mt-4 text-xs text-stone-400">
        Figures extracted from filed accounts. See the Financials tab for full
        detail, derived metrics, and source references.
      </p>
    </div>
  );
}

function MetricItem({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  return (
    <div>
      <dt className="text-xs text-stone-400">{label}</dt>
      <dd className="mt-0.5 tabular-nums text-base font-medium text-stone-900">
        {value ?? <NullState inline reason="Not extracted from accounts" />}
      </dd>
    </div>
  );
}

// ---- Narrative card --------------------------------------------------------

function NarrativeCard({ aiSummary }: { aiSummary: AiNarrativeSummary | null }) {
  if (!aiSummary) {
    return (
      <section aria-labelledby="narrative-heading">
        <div className="rounded-lg border border-stone-200 bg-white">
          <div className="border-b border-stone-100 px-5 py-4">
            <h2
              id="narrative-heading"
              className="text-sm font-semibold text-stone-900"
            >
              Summary
            </h2>
          </div>
          <div className="px-5 py-4">
            <NullState
              reason="Summary not available."
              className="border-0 bg-transparent p-0 text-left"
            />
          </div>
        </div>
      </section>
    );
  }

  const isTemplate = aiSummary.source === "template";

  return (
    <section aria-labelledby="narrative-heading">
      <div className="rounded-lg border border-stone-200 bg-white">
        <div className="flex items-center justify-between border-b border-stone-100 px-5 py-4">
          <h2
            id="narrative-heading"
            className="text-sm font-semibold text-stone-900"
          >
            Summary
          </h2>
          {isTemplate && (
            <span className="text-xs text-stone-400">Template</span>
          )}
        </div>

        <div className="space-y-4 px-5 py-4">
          {/* Short summary */}
          <p className="text-sm leading-relaxed text-stone-700">
            {aiSummary.summary_short}
          </p>

          {/* Key observations */}
          {aiSummary.key_observations.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-stone-400">
                Key observations
              </p>
              <ul className="space-y-1.5">
                {aiSummary.key_observations.map((obs, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <ObservationDot severity={obs.severity} />
                    <span className="text-stone-700">{obs.observation}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Data quality note */}
          {aiSummary.data_quality_note && (
            <p className="text-xs text-stone-400">{aiSummary.data_quality_note}</p>
          )}

          {/* Caveats */}
          {aiSummary.caveats.length > 0 && (
            <div className="border-t border-stone-100 pt-3">
              <ul className="space-y-1">
                {aiSummary.caveats.map((caveat, i) => (
                  <li key={i} className="text-xs text-stone-400">
                    {caveat}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function ObservationDot({ severity }: { severity: string }) {
  const colorMap: Record<string, string> = {
    high: "bg-red-400",
    medium: "bg-amber-400",
    low: "bg-blue-400",
    info: "bg-stone-300",
    positive: "bg-emerald-400",
  };
  const color = colorMap[severity] ?? "bg-stone-300";
  return (
    <span
      className={cn("mt-1.5 inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full", color)}
      aria-hidden="true"
    />
  );
}

// ---- Compliance card -------------------------------------------------------

function ComplianceCard({ overview }: { overview: CompanyOverview }) {
  return (
    <section aria-labelledby="compliance-heading">
      <div className="rounded-lg border border-stone-200 bg-white">
        <div className="border-b border-stone-100 px-4 py-3">
          <h2
            id="compliance-heading"
            className="text-sm font-semibold text-stone-900"
          >
            Filing compliance
          </h2>
        </div>
        <dl className="divide-y divide-stone-100 px-4">
          <ComplianceRow
            label="Accounts due"
            value={formatDate(overview.accounts_next_due)}
            alert={overview.accounts_overdue ?? false}
            alertLabel="Overdue"
          />
          <ComplianceRow
            label="Confirmation statement due"
            value={formatDate(overview.confirmation_statement_next_due)}
            alert={overview.confirmation_statement_overdue ?? false}
            alertLabel="Overdue"
          />
        </dl>
      </div>
    </section>
  );
}

function ComplianceRow({
  label,
  value,
  alert,
  alertLabel,
}: {
  label: string;
  value: string | null;
  alert: boolean;
  alertLabel: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-3">
      <dt className="text-xs text-stone-500">{label}</dt>
      <dd className="flex items-center gap-1.5">
        {value ? (
          <span
            className={cn(
              "text-xs font-medium tabular-nums",
              alert ? "text-red-700" : "text-stone-700",
            )}
          >
            {value}
          </span>
        ) : (
          <span className="text-xs text-stone-400 italic">Unknown</span>
        )}
        {alert && (
          <span className="rounded bg-red-50 px-1.5 py-0.5 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-200">
            {alertLabel}
          </span>
        )}
      </dd>
    </div>
  );
}

// ---- Freshness card --------------------------------------------------------

function FreshnessCard({ freshness }: { freshness: Freshness }) {
  return (
    <section aria-labelledby="freshness-heading">
      <div className="rounded-lg border border-stone-200 bg-white">
        <div className="border-b border-stone-100 px-4 py-3">
          <h2
            id="freshness-heading"
            className="text-sm font-semibold text-stone-900"
          >
            Data freshness
          </h2>
        </div>
        <dl className="divide-y divide-stone-100 px-4">
          <FreshnessRow label="Source last checked">
            <FreshnessTag
              lastCheckedAt={freshness.source_last_checked_at}
              freshnessStatus={freshness.freshness_status}
            />
          </FreshnessRow>
          {freshness.snapshot_generated_at && (
            <FreshnessRow label="Analysis generated">
              <FreshnessTag lastCheckedAt={freshness.snapshot_generated_at} />
            </FreshnessRow>
          )}
          {freshness.methodology_version && (
            <FreshnessRow label="Methodology">
              <span className="mono-id text-stone-500">
                {freshness.methodology_version}
              </span>
            </FreshnessRow>
          )}
        </dl>
      </div>
    </section>
  );
}

function FreshnessRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-3">
      <dt className="text-xs text-stone-500">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

// ---- SIC codes card --------------------------------------------------------

function SicCard({ codes }: { codes: string[] }) {
  return (
    <section aria-labelledby="sic-heading">
      <div className="rounded-lg border border-stone-200 bg-white">
        <div className="border-b border-stone-100 px-4 py-3">
          <h2
            id="sic-heading"
            className="text-sm font-semibold text-stone-900"
          >
            SIC codes
          </h2>
        </div>
        <ul className="divide-y divide-stone-100 px-4">
          {codes.map((code) => (
            <li key={code} className="py-2.5 font-mono text-xs text-stone-600">
              {code}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
