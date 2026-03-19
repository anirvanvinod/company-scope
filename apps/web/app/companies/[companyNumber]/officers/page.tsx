/**
 * Officers tab — /companies/[companyNumber]/officers
 *
 * Displays current and resigned officers with:
 *   - Name, role, nationality, country of residence
 *   - Appointment and resignation dates
 *   - Status filter (all / active / resigned) via URL param
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";

import { getOfficers } from "@/lib/api";
import { formatDate, formatRole } from "@/lib/utils";
import { NullState } from "@/components/ui/NullState";
import type { OfficerItem } from "@/lib/types";

interface PageProps {
  params: Promise<{ companyNumber: string }>;
  searchParams: Promise<{ status?: string }>;
}

export const metadata: Metadata = { title: "Officers" };

export default async function OfficersPage({ params, searchParams }: PageProps) {
  const { companyNumber } = await params;
  const { status } = await searchParams;

  // Validate status param
  const validStatus = status === "active" || status === "resigned" ? status : undefined;

  const { items, error, isNotFound } = await getOfficers(companyNumber, {
    status: validStatus,
  });

  if (isNotFound) notFound();

  const base = `/companies/${companyNumber}/officers`;

  const statusFilters: Array<{ value: string | undefined; label: string }> = [
    { value: undefined, label: "All" },
    { value: "active", label: "Current" },
    { value: "resigned", label: "Resigned" },
  ];

  if (error && items.length === 0) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <NullState reason={`Could not load officers: ${error}`} />
      </main>
    );
  }

  const currentOfficers = items.filter((o) => o.is_current);
  const resignedOfficers = items.filter((o) => !o.is_current);

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
      {/* Officer list                                                        */}
      {/* ------------------------------------------------------------------ */}
      {items.length === 0 ? (
        <NullState reason="No officers found." />
      ) : (
        <div className="space-y-8">
          {/* Current officers */}
          {(!validStatus || validStatus === "active") && currentOfficers.length > 0 && (
            <section aria-labelledby="current-heading">
              <h2
                id="current-heading"
                className="mb-3 text-xs font-medium uppercase tracking-wide text-stone-400"
              >
                Current ({currentOfficers.length})
              </h2>
              <OfficerTable officers={currentOfficers} />
            </section>
          )}

          {/* Resigned officers */}
          {(!validStatus || validStatus === "resigned") && resignedOfficers.length > 0 && (
            <section aria-labelledby="resigned-heading">
              <h2
                id="resigned-heading"
                className="mb-3 text-xs font-medium uppercase tracking-wide text-stone-400"
              >
                Resigned ({resignedOfficers.length})
              </h2>
              <OfficerTable officers={resignedOfficers} />
            </section>
          )}
        </div>
      )}

      <p className="mt-8 text-xs text-stone-400">
        Officer appointments sourced from Companies House public data.
      </p>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function OfficerTable({ officers }: { officers: OfficerItem[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-stone-200">
      <table className="min-w-full divide-y divide-stone-200 bg-white text-sm">
        <thead className="bg-stone-50">
          <tr>
            <th className="py-3 pl-5 pr-4 text-left text-xs font-medium text-stone-500">
              Name
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-stone-500">
              Role
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-stone-500">
              Nationality
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-stone-500">
              Appointed
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-stone-500">
              Resigned
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {officers.map((officer, i) => (
            <OfficerRow key={i} officer={officer} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OfficerRow({ officer }: { officer: OfficerItem }) {
  const dob =
    officer.date_of_birth_month && officer.date_of_birth_year
      ? `b. ${officer.date_of_birth_year}`
      : null;

  return (
    <tr className="hover:bg-stone-50">
      <td className="py-3 pl-5 pr-4">
        <span className="font-medium text-stone-900">{officer.name}</span>
        {dob && (
          <span className="ml-2 text-xs text-stone-400">{dob}</span>
        )}
        {officer.occupation && (
          <p className="mt-0.5 text-xs text-stone-400">{officer.occupation}</p>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-stone-600">
        {formatRole(officer.role) ?? officer.role ?? "—"}
      </td>
      <td className="px-4 py-3 text-xs text-stone-600">
        {officer.nationality ?? <span className="text-stone-300">—</span>}
      </td>
      <td className="px-4 py-3 tabular-nums text-xs text-stone-600">
        {formatDate(officer.appointed_on) ?? <span className="text-stone-300">—</span>}
      </td>
      <td className="px-4 py-3 tabular-nums text-xs text-stone-600">
        {officer.is_current ? (
          <span className="text-emerald-700">Current</span>
        ) : (
          formatDate(officer.resigned_on) ?? <span className="text-stone-300">—</span>
        )}
      </td>
    </tr>
  );
}
