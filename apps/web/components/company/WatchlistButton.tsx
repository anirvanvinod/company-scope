/**
 * WatchlistButton — client component for adding/removing a company from
 * the user's default watchlist.
 *
 * Props are computed server-side in the company overview page so the
 * initial state is correct without a client-side fetch on mount.
 *
 * - isWatched + watchlistId: from server-rendered initial state
 * - unauthenticated: button links to /sign-in
 */

"use client";

import { useTransition } from "react";

import { addToWatchlist, removeFromWatchlist } from "@/lib/watchlist-actions";

interface WatchlistButtonProps {
  companyNumber: string;
  isWatched: boolean;
  /** UUID of the watchlist that contains the company (when isWatched=true)
   *  or the default watchlist to add to (when isWatched=false). Null if the
   *  user has no watchlists (rare edge case). */
  watchlistId: string | null;
  /** Not signed in — show sign-in prompt instead of toggle */
  unauthenticated?: boolean;
}

export function WatchlistButton({
  companyNumber,
  isWatched,
  watchlistId,
  unauthenticated = false,
}: WatchlistButtonProps) {
  const [isPending, startTransition] = useTransition();

  if (unauthenticated) {
    return (
      <a
        href={`/sign-in?next=/companies/${companyNumber}`}
        className="flex items-center gap-1.5 rounded-md border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-500 hover:border-stone-300 hover:text-stone-700"
      >
        <BookmarkIcon filled={false} />
        Save
      </a>
    );
  }

  if (!watchlistId) return null;

  function handleToggle() {
    startTransition(async () => {
      if (isWatched) {
        await removeFromWatchlist(watchlistId!, companyNumber);
      } else {
        await addToWatchlist(watchlistId!, companyNumber);
      }
    });
  }

  return (
    <button
      onClick={handleToggle}
      disabled={isPending}
      className={
        isWatched
          ? "flex items-center gap-1.5 rounded-md border border-stone-300 bg-stone-100 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-200 disabled:opacity-50"
          : "flex items-center gap-1.5 rounded-md border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-500 hover:border-stone-300 hover:text-stone-700 disabled:opacity-50"
      }
      aria-label={isWatched ? "Remove from watchlist" : "Save to watchlist"}
    >
      <BookmarkIcon filled={isWatched} />
      {isPending ? "…" : isWatched ? "Saved" : "Save"}
    </button>
  );
}

function BookmarkIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 16 16"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 2h10v13l-5-3-5 3V2z" />
    </svg>
  );
}
