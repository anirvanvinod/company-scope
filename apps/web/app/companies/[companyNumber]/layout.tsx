/**
 * Company route layout.
 *
 * Fetches company identity data and renders the shared company header and
 * tab navigation for all pages under /companies/[companyNumber]/*.
 *
 * Next.js deduplicates the getCompany() fetch: if page.tsx or any sub-page
 * also calls getCompany(), only one network request is made per render cycle.
 */

import { notFound } from "next/navigation";
import Link from "next/link";

import { getCompany } from "@/lib/api";
import { formatCompanyType } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { CompanyTabNav } from "@/components/layout/CompanyTabNav";

interface LayoutProps {
  children: React.ReactNode;
  params: Promise<{ companyNumber: string }>;
}

export default async function CompanyLayout({ children, params }: LayoutProps) {
  const { companyNumber } = await params;
  const { data, isNotFound } = await getCompany(companyNumber);

  if (isNotFound || !data) notFound();

  const { company } = data;
  const base = `/companies/${companyNumber}`;

  return (
    <div className="flex flex-1 flex-col">
      {/* ---------------------------------------------------------------- */}
      {/* Company header                                                   */}
      {/* ---------------------------------------------------------------- */}
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
          {/* Breadcrumb */}
          <p className="mb-2.5 text-xs text-stone-400">
            <Link href="/search" className="hover:text-stone-600">
              Search
            </Link>{" "}
            /{" "}
            <span className="mono-id">{companyNumber}</span>
          </p>

          {/* Company name + status badge */}
          <div className="flex flex-wrap items-start gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-stone-900">
              {company.company_name}
            </h1>
            {company.company_status && (
              <div className="mt-0.5">
                <StatusBadge status={company.company_status} />
              </div>
            )}
          </div>

          {/* Meta row */}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm text-stone-500">
            <span className="mono-id text-stone-400">{companyNumber}</span>
            {company.company_type && (
              <>
                <span className="text-stone-300">·</span>
                <span>
                  {formatCompanyType(company.company_type) ?? company.company_type}
                </span>
              </>
            )}
            {company.jurisdiction && (
              <>
                <span className="text-stone-300">·</span>
                <span className="capitalize">
                  {company.jurisdiction.replace(/-/g, " ")}
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Tab navigation                                                   */}
      {/* ---------------------------------------------------------------- */}
      <nav className="border-b border-stone-200 bg-white" aria-label="Company sections">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <CompanyTabNav base={base} />
        </div>
      </nav>

      {/* ---------------------------------------------------------------- */}
      {/* Page content                                                     */}
      {/* ---------------------------------------------------------------- */}
      <div className="flex-1">{children}</div>
    </div>
  );
}
