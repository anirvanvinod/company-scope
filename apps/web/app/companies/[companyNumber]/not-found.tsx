/**
 * Not-found page for /companies/[companyNumber].
 * Shown when layout.tsx calls notFound() because the company doesn't exist.
 */

import Link from "next/link";

export default function CompanyNotFound() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-md text-center">
        <p className="text-sm font-medium text-stone-500">Company not found</p>
        <p className="mt-2 text-xs text-stone-400">
          No company with this number exists in our database. It may not have
          been ingested yet, or the number may be incorrect.
        </p>
        <Link
          href="/search"
          className="mt-6 inline-block rounded-md bg-stone-900 px-4 py-2 text-sm text-white hover:bg-stone-700"
        >
          Back to search
        </Link>
      </div>
    </div>
  );
}
