/**
 * Watchlist mutation Server Actions.
 *
 * Called from WatchlistButton (client component). Running on the
 * Next.js server, they forward the cs_session cookie as a Bearer token
 * to the FastAPI watchlist endpoints, then revalidate the affected path.
 */

"use server";

import { revalidatePath } from "next/cache";

import { getAuthHeader } from "./auth";

function apiBase(): string {
  return (
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000"
  );
}

export async function addToWatchlist(
  watchlistId: string,
  companyNumber: string,
): Promise<{ error: string | null }> {
  const authHeader = await getAuthHeader();
  if (!("Authorization" in authHeader)) {
    return { error: "Not signed in" };
  }

  try {
    const res = await fetch(
      `${apiBase()}/api/v1/watchlists/${watchlistId}/items`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ company_number: companyNumber }),
        cache: "no-store",
      },
    );

    if (!res.ok) {
      const json = await res.json().catch(() => ({}));
      return { error: json.error?.message ?? "Could not save company." };
    }
  } catch {
    return { error: "Network error. Please try again." };
  }

  revalidatePath(`/companies/${companyNumber}`);
  return { error: null };
}

export async function removeFromWatchlist(
  watchlistId: string,
  companyNumber: string,
): Promise<{ error: string | null }> {
  const authHeader = await getAuthHeader();
  if (!("Authorization" in authHeader)) {
    return { error: "Not signed in" };
  }

  try {
    const res = await fetch(
      `${apiBase()}/api/v1/watchlists/${watchlistId}/items/${companyNumber}`,
      {
        method: "DELETE",
        headers: authHeader,
        cache: "no-store",
      },
    );

    if (!res.ok) {
      const json = await res.json().catch(() => ({}));
      return { error: json.error?.message ?? "Could not remove company." };
    }
  } catch {
    return { error: "Network error. Please try again." };
  }

  revalidatePath(`/companies/${companyNumber}`);
  return { error: null };
}
