/**
 * Home page — search-first entry point.
 *
 * Design intent (docs/11-ui-ux-principles.md §Search-first):
 *   - Search is the primary action; everything else is secondary
 *   - No marketing superlatives; describe what the product does plainly
 *   - Standard caveat visible without requiring a click
 */

import { SearchBox } from "@/components/search/SearchBox";

export default function HomePage() {
  return (
    <main className="flex flex-1 flex-col">
      {/* ---------------------------------------------------------------- */}
      {/* Hero — search is the entire above-the-fold experience             */}
      {/* ---------------------------------------------------------------- */}
      <section className="flex flex-1 flex-col items-center justify-center px-4 pb-16 pt-12">
        <div className="w-full max-w-xl">
          <h1 className="mb-2 text-center text-2xl font-semibold tracking-tight text-stone-900">
            Search UK companies
          </h1>
          <p className="mb-7 text-center text-sm text-stone-500">
            Company filings, financial history, officers, and risk signals —
            sourced from Companies House public data.
          </p>

          <SearchBox size="large" autoFocus />

          <p className="mt-3 text-center text-xs text-stone-400">
            Try a company name or number — for example{" "}
            <ExampleLink q="Tesco PLC" /> or{" "}
            <ExampleLink q="00445790" />
          </p>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* What you get — three plain text panels, no icons or hype          */}
      {/* ---------------------------------------------------------------- */}
      <section className="border-t border-stone-200 bg-white">
        <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="grid gap-8 sm:grid-cols-3">
            <ValuePanel
              heading="Company profile"
              body="Status, incorporation date, officers, persons with significant
                control, and registered charges — all read directly from
                Companies House."
            />
            <ValuePanel
              heading="Financial history"
              body="Revenue, net assets, and key metrics extracted from filed
                accounts, with confidence indicators showing how reliably each
                figure was parsed."
            />
            <ValuePanel
              heading="Risk signals"
              body="Rule-based signals for late filings, governance changes, and
                financial indicators. Each signal is explained and linked to its
                source."
            />
          </div>

          <p className="mt-10 text-center text-xs text-stone-400">
            Based on public data from Companies House.{" "}
            <span className="text-stone-500">
              Not investment advice, legal advice, or a regulated credit score.
            </span>
          </p>
        </div>
      </section>
    </main>
  );
}

function ValuePanel({ heading, body }: { heading: string; body: string }) {
  return (
    <div>
      <h2 className="mb-1.5 text-sm font-semibold text-stone-800">{heading}</h2>
      <p className="text-sm leading-relaxed text-stone-500">{body}</p>
    </div>
  );
}

function ExampleLink({ q }: { q: string }) {
  return (
    <a
      href={`/search?q=${encodeURIComponent(q)}`}
      className="text-blue-700 underline-offset-2 hover:underline"
    >
      {q}
    </a>
  );
}
