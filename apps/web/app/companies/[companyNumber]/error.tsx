"use client";

/**
 * Error boundary for /companies/[companyNumber]/* routes.
 * Catches render-time errors thrown by any sub-page under this segment.
 */

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function CompanyError({ error, reset }: ErrorProps) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-md text-center">
        <p className="text-sm font-medium text-stone-500">Something went wrong</p>
        <p className="mt-2 text-xs text-stone-400">
          {error.message || "An unexpected error occurred while loading this page."}
        </p>
        {error.digest && (
          <p className="mt-1 font-mono text-xs text-stone-300">
            ref: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          className="mt-6 rounded-md bg-stone-900 px-4 py-2 text-sm text-white hover:bg-stone-700"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
