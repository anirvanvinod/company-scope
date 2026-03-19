/**
 * Filings tab — /companies/[companyNumber]/filings
 *
 * Displays the filing timeline with:
 *   - Category, type, description, action date
 *   - Parse status indicator (parsed / unparsed / pending)
 *   - Source document links where available
 *   - URL-based cursor pagination (no JS required)
 *
 * Pagination: next cursor is passed as ?cursor=<base64> in the URL.
 * This is a server component; the link to the next page is a plain <a> tag.
 */

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";

import { getFilings } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { NullState } from "@/components/ui/NullState";
import type { FilingItem } from "@/lib/types";

interface PageProps {
  params: Promise<{ companyNumber: string }>;
  searchParams: Promise<{ cursor?: string; category?: string }>;
}

export const metadata: Metadata = { title: "Filings" };

const CATEGORY_LABELS: Record<string, string> = {
  accounts: "Accounts",
  "confirmation-statement": "Confirmation statement",
  "incorporation": "Incorporation",
  "officers": "Officers",
  "persons-with-significant-control": "PSC",
  "charges": "Charges",
  "insolvency": "Insolvency",
  "dissolution": "Dissolution",
  "capital": "Capital",
  "address": "Address",
  "other": "Other",
};

const PARSE_STATUS_LABELS: Record<string, { label: string; className: string }> = {
  parsed: {
    label: "Parsed",
    className: "text-emerald-700 bg-emerald-50 ring-emerald-200",
  },
  pending: {
    label: "Pending",
    className: "text-amber-700 bg-amber-50 ring-amber-200",
  },
  failed: {
    label: "Parse failed",
    className: "text-red-700 bg-red-50 ring-red-200",
  },
  not_applicable: {
    label: "N/A",
    className: "text-stone-400 bg-stone-50 ring-stone-200",
  },
};

export default async function FilingsPage({ params, searchParams }: PageProps) {
  const { companyNumber } = await params;
  const { cursor, category } = await searchParams;

  const { items, nextCursor, error, isNotFound } = await getFilings(companyNumber, {
    cursor,
    limit: 25,
    category,
  });

  if (isNotFound) notFound();

  const base = `/companies/${companyNumber}/filings`;

  // Build category filter URL helper
  function categoryUrl(cat: string | undefined) {
    const params = new URLSearchParams();
    if (cat) params.set("category", cat);
    const qs = params.toString();
    return qs ? `${base}?${qs}` : base;
  }

  // Available category filter values
  const categoryFilters = [
    undefined,
    "accounts",
    "confirmation-statement",
    "officers",
    "persons-with-significant-control",
    "charges",
    "insolvency",
    "other",
  ];

  if (error && items.length === 0) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <NullState reason={`Could not load filings: ${error}`} />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* ------------------------------------------------------------------ */}
      {/* Category filter strip                                              */}
      {/* ------------------------------------------------------------------ */}
      <div className="mb-6 flex flex-wrap gap-2">
        {categoryFilters.map((cat) => {
          const isActive = category === cat;
          return (
            <Link
              key={cat ?? "all"}
              href={categoryUrl(cat)}
              className={
                isActive
                  ? "rounded-full bg-stone-900 px-3 py-1 text-xs font-medium text-white"
                  : "rounded-full border border-stone-200 bg-white px-3 py-1 text-xs text-stone-600 hover:border-stone-300"
              }
            >
              {cat ? (CATEGORY_LABELS[cat] ?? cat) : "All"}
            </Link>
          );
        })}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Filing list                                                         */}
      {/* ------------------------------------------------------------------ */}
      {items.length === 0 ? (
        <NullState reason="No filings found for this filter." />
      ) : (
        <div className="rounded-lg border border-stone-200 bg-white">
          <ul className="divide-y divide-stone-100">
            {items.map((filing) => (
              <FilingRow key={filing.transaction_id} filing={filing} />
            ))}
          </ul>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Pagination                                                          */}
      {/* ------------------------------------------------------------------ */}
      {nextCursor && (
        <div className="mt-6 flex justify-center">
          <Link
            href={`${base}?cursor=${encodeURIComponent(nextCursor)}${category ? `&category=${category}` : ""}`}
            className="rounded-md border border-stone-200 bg-white px-4 py-2 text-sm text-stone-600 hover:border-stone-300"
          >
            Load more
          </Link>
        </div>
      )}

      <p className="mt-6 text-xs text-stone-400">
        Filing history sourced from Companies House public data. Document links
        open the original filing PDF on companieshouse.gov.uk.
      </p>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FilingRow({ filing }: { filing: FilingItem }) {
  const parseInfo = filing.parse_status
    ? (PARSE_STATUS_LABELS[filing.parse_status] ?? null)
    : null;

  const docUrl = filing.source_links?.["document_url"] ?? null;
  const viewerUrl = filing.source_links?.["viewer_url"] ?? null;
  const linkHref = viewerUrl ?? docUrl;

  return (
    <li className="px-5 py-4">
      <div className="flex items-start justify-between gap-4">
        {/* Left: date + category */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {/* Action date */}
            <span className="tabular-nums text-xs text-stone-400">
              {formatDate(filing.action_date) ?? formatDate(filing.date_filed) ?? "Unknown date"}
            </span>

            {/* Category badge */}
            {filing.category && (
              <span className="text-xs text-stone-500">
                {CATEGORY_LABELS[filing.category] ?? filing.category}
              </span>
            )}

            {/* Type */}
            {filing.type && (
              <>
                <span className="text-stone-300">·</span>
                <span className="font-mono text-xs text-stone-400">{filing.type}</span>
              </>
            )}

            {/* Parse status */}
            {parseInfo && (
              <span
                className={`rounded px-1.5 py-0.5 text-xs ring-1 ring-inset ${parseInfo.className}`}
              >
                {parseInfo.label}
              </span>
            )}

            {/* Pages */}
            {filing.pages !== null && filing.pages !== undefined && (
              <span className="text-xs text-stone-300">
                {filing.pages}p
              </span>
            )}
          </div>

          {/* Description */}
          {filing.description && (
            <p className="mt-1 text-sm text-stone-700">{filing.description}</p>
          )}
        </div>

        {/* Right: document link */}
        {linkHref && (
          <a
            href={linkHref}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 text-xs text-stone-400 underline-offset-2 hover:text-stone-700 hover:underline"
          >
            View
          </a>
        )}
      </div>
    </li>
  );
}
