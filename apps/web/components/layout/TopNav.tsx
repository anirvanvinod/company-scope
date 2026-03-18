/**
 * TopNav — global navigation bar.
 *
 * Server component. The search form uses a plain HTML GET action so it
 * works without JavaScript and requires no client-side router.
 */

import Link from "next/link";

export function TopNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-stone-200 bg-white/95 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:gap-6 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link
          href="/"
          className="flex-shrink-0 text-sm font-semibold tracking-tight text-stone-900 hover:text-stone-700"
        >
          CompanyScope
        </Link>

        {/* Search bar */}
        <form action="/search" method="GET" className="flex flex-1 max-w-lg">
          <div className="relative flex w-full items-center">
            <label htmlFor="nav-search" className="sr-only">
              Search companies
            </label>
            <input
              id="nav-search"
              type="search"
              name="q"
              placeholder="Company name or number…"
              className="w-full rounded-md border border-stone-300 bg-white py-1.5 pl-3 pr-9 text-sm text-stone-900 placeholder-stone-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
              autoComplete="off"
            />
            <button
              type="submit"
              className="absolute right-2 text-stone-400 hover:text-stone-600"
              aria-label="Search"
            >
              <SearchIcon />
            </button>
          </div>
        </form>

        {/* Nav links */}
        <nav className="ml-auto flex items-center gap-5 text-sm">
          <Link
            href="/methodology"
            className="hidden text-stone-500 hover:text-stone-900 sm:block"
          >
            Methodology
          </Link>
        </nav>
      </div>
    </header>
  );
}

function SearchIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M10.5 10.5L13 13"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
