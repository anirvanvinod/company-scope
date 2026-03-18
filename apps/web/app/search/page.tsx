/**
 * Search results page.
 *
 * Server component — fetches from the API at request time.
 * No loading spinners: Next.js streaming is used implicitly.
 *
 * URL: /search?q=<query>[&status=active|dissolved]
 */

import type { Metadata } from "next";
import Link from "next/link";

import { searchCompanies } from "@/lib/api";
import { formatDate, formatCompanyType } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { NullState } from "@/components/ui/NullState";

interface PageProps {
  searchParams: Promise<{
    q?: string;
    status?: string;
  }>;
}

export async function generateMetadata({
  searchParams,
}: PageProps): Promise<Metadata> {
  const { q } = await searchParams;
  return {
    title: q?.trim() ? `"${q.trim()}" — Search` : "Search",
  };
}

export default async function SearchPage({ searchParams }: PageProps) {
  const { q, status } = await searchParams;
  const query = q?.trim() ?? "";

  // Empty query — guide the user
  if (!query) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <h1 className="text-xl font-semibold text-stone-900">Search</h1>
        <p className="mt-2 text-sm text-stone-500">
          Enter a company name or number in the search bar above.
        </p>
      </main>
    );
  }

  const { items, error } = await searchCompanies(query, { status });

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      {/* Header row */}
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-stone-900">
          Results for{" "}
          <span className="text-stone-600">&ldquo;{query}&rdquo;</span>
        </h1>
        {!error && (
          <p className="mt-0.5 text-sm text-stone-500">
            {items.length === 0
              ? "No companies found"
              : items.length >= 25
                ? "Showing top 25 results"
                : `${items.length} result${items.length === 1 ? "" : "s"}`}
          </p>
        )}
      </div>

      {/* Status filter strip */}
      <div className="mb-5 flex gap-2 text-sm">
        <FilterLink href={`/search?q=${encodeURIComponent(query)}`} active={!status}>
          All
        </FilterLink>
        <FilterLink
          href={`/search?q=${encodeURIComponent(query)}&status=active`}
          active={status === "active"}
        >
          Active
        </FilterLink>
        <FilterLink
          href={`/search?q=${encodeURIComponent(query)}&status=dissolved`}
          active={status === "dissolved"}
        >
          Dissolved
        </FilterLink>
      </div>

      {/* Results / states */}
      {error ? (
        <NullState
          reason={`Could not load search results: ${error}. Please try again.`}
        />
      ) : items.length === 0 ? (
        <NullState reason="No companies matched this search. Try a different name, or search by company number." />
      ) : (
        <ul role="list" className="space-y-2">
          {items.map((item) => (
            <li key={item.company_number}>
              <Link
                href={`/companies/${item.company_number}`}
                className="group block rounded-lg border border-stone-200 bg-white px-5 py-4 transition-colors hover:border-stone-300 hover:bg-stone-50 focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    {/* Name + status */}
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-stone-900">
                        {item.company_name}
                      </span>
                      {item.company_status && (
                        <StatusBadge status={item.company_status} />
                      )}
                    </div>

                    {/* Meta row */}
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-stone-500">
                      <span className="mono-id text-stone-400">
                        {item.company_number}
                      </span>
                      {item.company_type && (
                        <span>
                          {formatCompanyType(item.company_type) ??
                            item.company_type}
                        </span>
                      )}
                      {item.registered_office_address_snippet && (
                        <span>{item.registered_office_address_snippet}</span>
                      )}
                      {item.date_of_creation && (
                        <span>
                          Incorporated {formatDate(item.date_of_creation)}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Chevron */}
                  <ChevronRight />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

// ---------------------------------------------------------------------------
// Small components
// ---------------------------------------------------------------------------

function FilterLink({
  href,
  active,
  children,
}: {
  href: string;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={
        active
          ? "rounded-md bg-stone-900 px-3 py-1.5 text-xs font-medium text-white"
          : "rounded-md border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-500 hover:border-stone-300 hover:text-stone-700"
      }
    >
      {children}
    </Link>
  );
}

function ChevronRight() {
  return (
    <svg
      className="mt-0.5 flex-shrink-0 text-stone-300 transition-colors group-hover:text-stone-400"
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M6 3l5 5-5 5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
