/**
 * Ownership tab — /companies/[companyNumber]/ownership
 *
 * Displays Persons with Significant Control (PSCs) with:
 *   - Name, kind (individual / corporate entity / legal person)
 *   - Natures of control (formatted list)
 *   - Notified on / ceased dates
 *   - Status filter (all / active / ceased)
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";

import { getPsc } from "@/lib/api";
import { formatDate, formatPscKind, formatNatureOfControl } from "@/lib/utils";
import { NullState } from "@/components/ui/NullState";
import type { PscItem } from "@/lib/types";

interface PageProps {
  params: Promise<{ companyNumber: string }>;
  searchParams: Promise<{ status?: string }>;
}

export const metadata: Metadata = { title: "Ownership" };

export default async function OwnershipPage({ params, searchParams }: PageProps) {
  const { companyNumber } = await params;
  const { status } = await searchParams;

  const validStatus = status === "active" || status === "ceased" ? status : undefined;

  const { items, error, isNotFound } = await getPsc(companyNumber, {
    status: validStatus,
  });

  if (isNotFound) notFound();

  const base = `/companies/${companyNumber}/ownership`;

  const statusFilters: Array<{ value: string | undefined; label: string }> = [
    { value: undefined, label: "All" },
    { value: "active", label: "Current" },
    { value: "ceased", label: "Ceased" },
  ];

  if (error && items.length === 0) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <NullState reason={`Could not load ownership data: ${error}`} />
      </main>
    );
  }

  const currentPscs = items.filter((p) => p.is_current);
  const ceasedPscs = items.filter((p) => !p.is_current);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
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
      {/* PSC list                                                            */}
      {/* ------------------------------------------------------------------ */}
      {items.length === 0 ? (
        <NullState
          reason={
            validStatus
              ? `No ${validStatus} PSCs found.`
              : "No persons with significant control on record."
          }
        />
      ) : (
        <div className="space-y-8">
          {(!validStatus || validStatus === "active") && currentPscs.length > 0 && (
            <section aria-labelledby="current-psc-heading">
              <h2
                id="current-psc-heading"
                className="mb-3 text-xs font-medium uppercase tracking-wide text-stone-400"
              >
                Current ({currentPscs.length})
              </h2>
              <div className="space-y-3">
                {currentPscs.map((psc, i) => (
                  <PscCard key={i} psc={psc} />
                ))}
              </div>
            </section>
          )}

          {(!validStatus || validStatus === "ceased") && ceasedPscs.length > 0 && (
            <section aria-labelledby="ceased-psc-heading">
              <h2
                id="ceased-psc-heading"
                className="mb-3 text-xs font-medium uppercase tracking-wide text-stone-400"
              >
                Ceased ({ceasedPscs.length})
              </h2>
              <div className="space-y-3">
                {ceasedPscs.map((psc, i) => (
                  <PscCard key={i} psc={psc} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      <p className="mt-8 text-xs text-stone-400">
        PSC data sourced from Companies House public register. Ownership
        percentages are provided as statutory bands, not precise figures.
      </p>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PscCard({ psc }: { psc: PscItem }) {
  const kindLabel = formatPscKind(psc.kind);
  const dob =
    psc.date_of_birth_month && psc.date_of_birth_year
      ? `b. ${psc.date_of_birth_year}`
      : null;

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        {/* Name + kind */}
        <div>
          <p className="font-medium text-stone-900">
            {psc.name ?? <span className="italic text-stone-400">Name restricted</span>}
          </p>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-stone-500">
            {kindLabel && <span>{kindLabel}</span>}
            {psc.nationality && (
              <>
                <span className="text-stone-300">·</span>
                <span>{psc.nationality}</span>
              </>
            )}
            {psc.country_of_residence && (
              <>
                <span className="text-stone-300">·</span>
                <span>{psc.country_of_residence}</span>
              </>
            )}
            {dob && (
              <>
                <span className="text-stone-300">·</span>
                <span>{dob}</span>
              </>
            )}
          </div>
        </div>

        {/* Status + dates */}
        <div className="text-right text-xs text-stone-400">
          {psc.is_current ? (
            <span className="text-emerald-700 font-medium">Current</span>
          ) : (
            <span className="text-stone-400">Ceased</span>
          )}
          {psc.notified_on && (
            <p className="mt-0.5">
              Notified {formatDate(psc.notified_on)}
            </p>
          )}
          {psc.ceased_on && (
            <p>Ceased {formatDate(psc.ceased_on)}</p>
          )}
        </div>
      </div>

      {/* Natures of control */}
      {psc.natures_of_control.length > 0 && (
        <div className="mt-3 border-t border-stone-100 pt-3">
          <p className="mb-1.5 text-xs font-medium text-stone-500">
            Nature of control
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {psc.natures_of_control.map((nature) => (
              <li
                key={nature}
                className="rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-600"
              >
                {formatNatureOfControl(nature)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
