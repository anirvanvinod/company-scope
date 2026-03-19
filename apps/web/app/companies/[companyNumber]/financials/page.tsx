/**
 * Financials tab — /companies/[companyNumber]/financials
 *
 * Sections:
 *   1. Period facts table  — rows = canonical facts, columns = periods (newest first)
 *   2. Derived metrics     — grid of computed ratios with confidence
 *   3. Trend charts        — SVG MiniChart for revenue and net_assets_liabilities series
 *
 * Data quality:
 *   - ConfidencePip shown per period and per metric
 *   - Null values shown as "—" (NullState inline) never zero-filled
 *   - Extraction method shown in tooltip on confidence pip
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { getFinancials } from "@/lib/api";
import {
  formatDate,
  formatCurrency,
  formatNumber,
  formatAccountsType,
  formatFactName,
  formatMetricName,
  formatMetricDescription,
} from "@/lib/utils";
import { ConfidencePip } from "@/components/ui/ConfidencePip";
import { NullState } from "@/components/ui/NullState";
import { MiniChart } from "@/components/ui/MiniChart";
import type { PeriodFacts, FactDetail } from "@/lib/types";

interface PageProps {
  params: Promise<{ companyNumber: string }>;
}

export const metadata: Metadata = { title: "Financials" };

// Canonical fact order for the table rows
const FACT_ORDER = [
  "revenue",
  "gross_profit",
  "operating_profit",
  "profit_loss_after_tax",
  "current_assets",
  "fixed_assets",
  "total_assets_less_current_liabilities",
  "creditors_within_one_year",
  "creditors_after_one_year",
  "net_assets_liabilities",
  "cash",
  "average_number_of_employees",
];

export default async function FinancialsPage({ params }: PageProps) {
  const { companyNumber } = await params;
  const { data, error, isNotFound } = await getFinancials(companyNumber, 5);

  if (isNotFound) notFound();

  if (!data) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <NullState
          reason={`Could not load financials${error ? `: ${error}` : ""}. Please try again.`}
        />
      </main>
    );
  }

  const { periods, derived_metrics, series, data_quality } = data;

  if (data_quality.message || periods.length === 0) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <NullState
          reason={
            data_quality.message ??
            "No financial data available. Accounts may not have been filed or parsed yet."
          }
        />
      </main>
    );
  }

  // Sort newest first
  const sortedPeriods = [...periods].sort(
    (a, b) => b.period_end.localeCompare(a.period_end),
  );

  // Collect all fact names present across all periods, in canonical order first
  const allFactNames = [
    ...FACT_ORDER.filter((k) =>
      sortedPeriods.some((p) => k in p.facts),
    ),
    ...sortedPeriods
      .flatMap((p) => Object.keys(p.facts))
      .filter((k, i, arr) => !FACT_ORDER.includes(k) && arr.indexOf(k) === i),
  ];

  // Primary period currency
  const primaryCurrency = sortedPeriods[0]?.currency_code ?? null;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="space-y-10">
        {/* ---------------------------------------------------------------- */}
        {/* Period facts table                                               */}
        {/* ---------------------------------------------------------------- */}
        <section aria-labelledby="facts-heading">
          <h2 id="facts-heading" className="mb-4 text-sm font-semibold text-stone-900">
            Period facts
          </h2>

          {/* Data quality note */}
          {data_quality.primary_period_facts_available !== undefined && (
            <p className="mb-3 text-xs text-stone-400">
              {data_quality.periods_available} period
              {data_quality.periods_available !== 1 ? "s" : ""} available ·{" "}
              {data_quality.primary_period_facts_available} facts extracted in latest period
            </p>
          )}

          <div className="overflow-x-auto rounded-lg border border-stone-200">
            <table className="min-w-full divide-y divide-stone-200 bg-white text-sm">
              <thead>
                <tr className="bg-stone-50">
                  <th className="py-3 pl-5 pr-4 text-left text-xs font-medium text-stone-500">
                    Fact
                  </th>
                  {sortedPeriods.map((p) => (
                    <th
                      key={p.period_id}
                      className="px-4 py-3 text-right text-xs font-medium text-stone-500"
                    >
                      <div>{formatDate(p.period_end)}</div>
                      {p.accounts_type && (
                        <div className="mt-0.5 font-normal text-stone-400">
                          {formatAccountsType(p.accounts_type) ?? p.accounts_type}
                        </div>
                      )}
                      <div className="mt-1 flex justify-end">
                        <ConfidencePip band={p.confidence_band} />
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {allFactNames.map((factName) => (
                  <FactRow
                    key={factName}
                    factName={factName}
                    periods={sortedPeriods}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-3 text-xs text-stone-400">
            Figures extracted from filed accounts at Companies House. Decimal
            values are as reported; no rounding is applied.
          </p>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Derived metrics                                                  */}
        {/* ---------------------------------------------------------------- */}
        {Object.keys(derived_metrics).length > 0 && (
          <section aria-labelledby="metrics-heading">
            <h2 id="metrics-heading" className="mb-4 text-sm font-semibold text-stone-900">
              Derived metrics
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(derived_metrics).map(([key, metric]) => {
                const description = formatMetricDescription(key);
                return (
                  <div
                    key={key}
                    className="rounded-lg border border-stone-200 bg-white p-4"
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <p className="text-xs font-medium text-stone-700">
                        {formatMetricName(key)}
                      </p>
                      <ConfidencePip band={metric.confidence_band} />
                    </div>
                    <p className="tabular-nums text-xl font-semibold text-stone-900">
                      {metric.value !== null
                        ? `${parseFloat(metric.value).toFixed(1)}${metric.unit}`
                        : "—"}
                    </p>
                    {description && (
                      <p className="mt-1.5 text-xs text-stone-400">{description}</p>
                    )}
                    {metric.warnings.length > 0 && (
                      <ul className="mt-2 space-y-0.5">
                        {metric.warnings.map((w, i) => (
                          <li key={i} className="text-xs text-amber-600">
                            {w}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="mt-3 text-xs text-stone-400">
              Derived metrics are calculated from extracted facts and are not
              audited ratios. Treat with appropriate caution.
            </p>
          </section>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Trend charts                                                     */}
        {/* ---------------------------------------------------------------- */}
        {Object.keys(series).length > 0 && (
          <section aria-labelledby="charts-heading">
            <h2 id="charts-heading" className="mb-4 text-sm font-semibold text-stone-900">
              Trends
            </h2>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              {Object.entries(series).map(([key, points]) => {
                if (points.length < 2) return null;
                return (
                  <div
                    key={key}
                    className="rounded-lg border border-stone-200 bg-white p-4"
                  >
                    <p className="mb-3 text-xs font-medium text-stone-700">
                      {formatFactName(key)}
                    </p>
                    <MiniChart
                      points={points}
                      currency={primaryCurrency}
                      label={formatFactName(key)}
                      height={90}
                    />
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FactRow({
  factName,
  periods,
}: {
  factName: string;
  periods: PeriodFacts[];
}) {
  return (
    <tr className="hover:bg-stone-50">
      <td className="py-2.5 pl-5 pr-4 text-xs text-stone-600">
        {formatFactName(factName)}
      </td>
      {periods.map((p) => {
        const fact: FactDetail | undefined = p.facts[factName];
        return (
          <td key={p.period_id} className="px-4 py-2.5 text-right">
            <FactCell fact={fact} currency={p.currency_code} />
          </td>
        );
      })}
    </tr>
  );
}

function FactCell({
  fact,
  currency,
}: {
  fact: FactDetail | undefined;
  currency: string | null | undefined;
}) {
  if (!fact) {
    return <span className="text-xs text-stone-300">—</span>;
  }
  if (fact.value === null) {
    return <NullState inline reason="Not extracted" />;
  }

  const num = parseFloat(fact.value);
  const isEmployees = fact.unit === "employees" || fact.unit === "count";

  let formatted: string;
  if (isEmployees) {
    formatted = formatNumber(fact.value) ?? fact.value;
  } else if (currency) {
    const sym =
      currency === "GBP" ? "£" : currency === "USD" ? "$" : currency === "EUR" ? "€" : "";
    formatted = `${sym}${new Intl.NumberFormat("en-GB").format(num)}`;
  } else {
    formatted = formatNumber(fact.value) ?? fact.value;
  }

  return (
    <span
      className="tabular-nums text-xs text-stone-800"
      title={fact.raw_label ?? undefined}
    >
      {formatted}
    </span>
  );
}
