/**
 * Charges tab — /companies/[companyNumber]/charges
 *
 * Displays registered charges (mortgages and debentures) with:
 *   - Status (outstanding / satisfied / partially satisfied)
 *   - Persons entitled (lenders)
 *   - Created / delivered / resolved dates
 *   - Status filter (all / outstanding / satisfied)
 *   - Context note: charges are a public financing indicator, not a risk signal by themselves
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";

import { getCharges } from "@/lib/api";
import { formatDate, formatChargeStatus } from "@/lib/utils";
import { NullState } from "@/components/ui/NullState";
import type { ChargeItem } from "@/lib/types";

interface PageProps {
  params: Promise<{ companyNumber: string }>;
  searchParams: Promise<{ status?: string }>;
}

export const metadata: Metadata = { title: "Charges" };

const STATUS_STYLES: Record<string, string> = {
  outstanding: "text-amber-700 bg-amber-50 ring-amber-200",
  "fully-satisfied": "text-stone-500 bg-stone-50 ring-stone-200",
  satisfied: "text-stone-500 bg-stone-50 ring-stone-200",
  "part-satisfied": "text-amber-700 bg-amber-50 ring-amber-200",
};

export default async function ChargesPage({ params, searchParams }: PageProps) {
  const { companyNumber } = await params;
  const { status } = await searchParams;

  const validStatus =
    status === "outstanding" || status === "satisfied" ? status : undefined;

  const { items, error, isNotFound } = await getCharges(companyNumber, {
    status: validStatus,
  });

  if (isNotFound) notFound();

  const base = `/companies/${companyNumber}/charges`;

  const statusFilters: Array<{ value: string | undefined; label: string }> = [
    { value: undefined, label: "All" },
    { value: "outstanding", label: "Outstanding" },
    { value: "satisfied", label: "Satisfied" },
  ];

  if (error && items.length === 0) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <NullState reason={`Could not load charges: ${error}`} />
      </main>
    );
  }

  const outstandingCount = items.filter(
    (c) => c.status === "outstanding" || c.status === "part-satisfied",
  ).length;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* ------------------------------------------------------------------ */}
      {/* Context note                                                        */}
      {/* ------------------------------------------------------------------ */}
      <div className="mb-6 rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
        <p className="text-xs text-stone-500">
          Registered charges indicate secured borrowing or other security interests
          against the company. The presence of charges is a normal part of business
          financing and is not itself a negative indicator.
          {outstandingCount > 0 && (
            <> There {outstandingCount === 1 ? "is" : "are"} currently{" "}
              <span className="font-medium text-stone-700">
                {outstandingCount} outstanding charge{outstandingCount !== 1 ? "s" : ""}
              </span>
              .
            </>
          )}
        </p>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Status filter                                                       */}
      {/* ------------------------------------------------------------------ */}
      <div className="mb-6 flex gap-2">
        {statusFilters.map(({ value, label }) => {
          const href = value ? `${base}?status=${value}` : base;
          const isActive = validStatus === value;
          return (
            <Link
              key={label}
              href={href}
              className={
                isActive
                  ? "rounded-full bg-stone-900 px-3 py-1 text-xs font-medium text-white"
                  : "rounded-full border border-stone-200 bg-white px-3 py-1 text-xs text-stone-600 hover:border-stone-300"
              }
            >
              {label}
            </Link>
          );
        })}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Charge list                                                         */}
      {/* ------------------------------------------------------------------ */}
      {items.length === 0 ? (
        <NullState
          reason={
            validStatus
              ? `No ${validStatus} charges found.`
              : "No registered charges on record."
          }
        />
      ) : (
        <div className="rounded-lg border border-stone-200 bg-white">
          <ul className="divide-y divide-stone-100">
            {items.map((charge) => (
              <ChargeRow key={charge.charge_id} charge={charge} />
            ))}
          </ul>
        </div>
      )}

      <p className="mt-6 text-xs text-stone-400">
        Charge data sourced from Companies House public register.
      </p>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ChargeRow({ charge }: { charge: ChargeItem }) {
  const statusLabel = formatChargeStatus(charge.status);
  const statusStyle = charge.status
    ? (STATUS_STYLES[charge.status] ?? "text-stone-500 bg-stone-50 ring-stone-200")
    : "text-stone-500 bg-stone-50 ring-stone-200";

  const persons = charge.persons_entitled ?? [];

  return (
    <li className="px-5 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          {/* Status + date row */}
          <div className="flex flex-wrap items-center gap-2">
            {statusLabel && (
              <span
                className={`rounded px-1.5 py-0.5 text-xs ring-1 ring-inset ${statusStyle}`}
              >
                {statusLabel}
              </span>
            )}
            {charge.delivered_on && (
              <span className="tabular-nums text-xs text-stone-400">
                Delivered {formatDate(charge.delivered_on)}
              </span>
            )}
            {charge.created_on && !charge.delivered_on && (
              <span className="tabular-nums text-xs text-stone-400">
                Created {formatDate(charge.created_on)}
              </span>
            )}
            {charge.resolved_on && (
              <span className="tabular-nums text-xs text-stone-400">
                · Satisfied {formatDate(charge.resolved_on)}
              </span>
            )}
          </div>

          {/* Persons entitled */}
          {persons.length > 0 && (
            <p className="mt-1.5 text-sm text-stone-700">
              {persons.map((p) => p.name).join(", ")}
            </p>
          )}

          {/* Charge ID */}
          <p className="mt-1 font-mono text-xs text-stone-300">
            {charge.charge_id}
          </p>
        </div>
      </div>
    </li>
  );
}
