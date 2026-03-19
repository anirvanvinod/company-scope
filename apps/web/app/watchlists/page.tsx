/**
 * Watchlists dashboard — /watchlists
 *
 * Protected by middleware.ts (redirects to /sign-in if no session cookie).
 *
 * Shows all of the user's watchlists with company counts, and allows
 * clicking through to see the companies within a watchlist.
 */

import type { Metadata } from "next";
import Link from "next/link";

import { getAuthHeader, getServerSession } from "@/lib/auth";
import { getWatchlistItems, getWatchlists } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { NullState } from "@/components/ui/NullState";
import type { WatchlistOut, WatchlistItemOut } from "@/lib/types";

export const metadata: Metadata = { title: "Watchlists" };

export default async function WatchlistsPage({
  searchParams,
}: {
  searchParams: Promise<{ list?: string }>;
}) {
  const { list: activeListId } = await searchParams;
  const user = await getServerSession();
  const authHeaders = await getAuthHeader();

  const { data: watchlists, error: wlError } = await getWatchlists(
    authHeaders as Record<string, string>,
  );

  const lists = watchlists ?? [];

  // If a specific list is selected (or default to first/default), load its items
  const activeList =
    lists.find((w) => w.id === activeListId) ??
    lists.find((w) => w.is_default) ??
    lists[0] ??
    null;

  let items: WatchlistItemOut[] = [];
  if (activeList) {
    const { data: wlData } = await getWatchlistItems(
      activeList.id,
      authHeaders as Record<string, string>,
    );
    items = wlData?.items ?? [];
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-stone-900">Watchlists</h1>
          {user && (
            <p className="mt-0.5 text-sm text-stone-400">{user.email}</p>
          )}
        </div>
      </div>

      {wlError && lists.length === 0 ? (
        <NullState reason={`Could not load watchlists: ${wlError}`} />
      ) : (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
          {/* ---- Sidebar: list of watchlists ---- */}
          <aside className="lg:col-span-1">
            <nav aria-label="Watchlists">
              {lists.length === 0 ? (
                <p className="text-sm text-stone-400">No watchlists yet.</p>
              ) : (
                <ul className="space-y-1">
                  {lists.map((wl) => (
                    <li key={wl.id}>
                      <Link
                        href={`/watchlists?list=${wl.id}`}
                        className={
                          activeList?.id === wl.id
                            ? "flex items-center justify-between rounded-md bg-stone-100 px-3 py-2 text-sm font-medium text-stone-900"
                            : "flex items-center justify-between rounded-md px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
                        }
                      >
                        <span className="min-w-0 truncate">{wl.name}</span>
                        <span className="ml-2 flex-shrink-0 tabular-nums text-xs text-stone-400">
                          {wl.item_count}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </nav>
          </aside>

          {/* ---- Main: items in active list ---- */}
          <section className="lg:col-span-3" aria-label="Companies in watchlist">
            {!activeList ? (
              <NullState reason="Select a watchlist to see its companies." />
            ) : (
              <>
                <div className="mb-4 flex items-center gap-3">
                  <h2 className="text-sm font-semibold text-stone-900">
                    {activeList.name}
                  </h2>
                  {activeList.is_default && (
                    <span className="rounded bg-stone-100 px-1.5 py-0.5 text-xs text-stone-500">
                      Default
                    </span>
                  )}
                </div>

                {items.length === 0 ? (
                  <NullState reason="No companies in this watchlist yet. Use the Save button on any company page to add one." />
                ) : (
                  <div className="rounded-lg border border-stone-200 bg-white">
                    <ul className="divide-y divide-stone-100">
                      {items.map((item) => (
                        <WatchlistItemRow key={item.company_number} item={item} />
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </main>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function WatchlistItemRow({ item }: { item: WatchlistItemOut }) {
  return (
    <li className="px-5 py-3">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <Link
            href={`/companies/${item.company_number}`}
            className="font-medium text-stone-900 hover:text-stone-600"
          >
            {item.company_name}
          </Link>
          <div className="mt-0.5 flex items-center gap-2">
            <span className="mono-id text-xs text-stone-400">
              {item.company_number}
            </span>
            {item.company_status && (
              <StatusBadge status={item.company_status} />
            )}
          </div>
        </div>
        <span className="flex-shrink-0 tabular-nums text-xs text-stone-400">
          Saved {formatDate(item.added_at)}
        </span>
      </div>
    </li>
  );
}
