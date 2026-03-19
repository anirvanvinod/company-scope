/**
 * Typed API client for the CompanyScope FastAPI backend.
 *
 * All functions are safe to call from server components (Node.js).
 * Do NOT import this module from "use client" components — use
 * NEXT_PUBLIC_API_URL directly in client components if needed.
 *
 * URL resolution:
 *   API_INTERNAL_URL   — Docker/server-internal route (not exposed to browser)
 *   NEXT_PUBLIC_API_URL — Browser-visible route (also available server-side)
 *   fallback            — http://localhost:8000 for local development
 */

import type {
  CompanyAggregate,
  SearchResultItem,
  FinancialsResponse,
  FilingItem,
  OfficerItem,
  PscItem,
  ChargeItem,
  WatchlistOut,
  WatchlistItemOut,
} from "./types";

function apiBase(): string {
  return (
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000"
  );
}

interface FetchResult<T> {
  data: T | null;
  error: string | null;
  isNotFound: boolean;
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<FetchResult<T>> {
  const url = `${apiBase()}${path}`;
  try {
    const res = await fetch(url, {
      cache: "no-store",
      ...init,
    });

    let json: { data?: T; error?: { code?: string; message?: string } };
    try {
      json = await res.json();
    } catch {
      return { data: null, error: `Invalid response from API (${res.status})`, isNotFound: false };
    }

    if (res.status === 404) {
      return {
        data: null,
        error: json.error?.message ?? "Not found",
        isNotFound: true,
      };
    }

    if (json.error) {
      return { data: null, error: json.error.message ?? "API error", isNotFound: false };
    }

    if (!res.ok) {
      return { data: null, error: `Request failed (${res.status})`, isNotFound: false };
    }

    return { data: json.data as T, error: null, isNotFound: false };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    return { data: null, error: message, isNotFound: false };
  }
}

// ---------------------------------------------------------------------------
// Public API functions
// ---------------------------------------------------------------------------

export async function searchCompanies(
  q: string,
  options: { limit?: number; status?: string } = {},
): Promise<{ items: SearchResultItem[]; error: string | null }> {
  const params = new URLSearchParams({
    q,
    limit: String(options.limit ?? 25),
  });
  if (options.status) params.set("status", options.status);

  const { data, error } = await apiFetch<SearchResultItem[]>(
    `/api/v1/search?${params.toString()}`,
  );
  return { items: data ?? [], error };
}

export async function getCompany(
  companyNumber: string,
): Promise<FetchResult<CompanyAggregate>> {
  return apiFetch<CompanyAggregate>(`/api/v1/companies/${companyNumber}`);
}

// ---------------------------------------------------------------------------
// List helper — extracts items + next_cursor from the paginated envelope
// ---------------------------------------------------------------------------

interface ListFetchResult<T> {
  items: T[];
  nextCursor: string | null;
  error: string | null;
  isNotFound: boolean;
}

async function apiFetchList<T>(
  path: string,
  init?: RequestInit,
): Promise<ListFetchResult<T>> {
  const url = `${apiBase()}${path}`;
  try {
    const res = await fetch(url, { cache: "no-store", ...init });
    let json: {
      data?: T[];
      meta?: { pagination?: { next_cursor?: string | null } };
      error?: { code?: string; message?: string };
    };
    try {
      json = await res.json();
    } catch {
      return { items: [], nextCursor: null, error: `Invalid response (${res.status})`, isNotFound: false };
    }
    if (res.status === 404) {
      return { items: [], nextCursor: null, error: json.error?.message ?? "Not found", isNotFound: true };
    }
    if (json.error) {
      return { items: [], nextCursor: null, error: json.error.message ?? "API error", isNotFound: false };
    }
    if (!res.ok) {
      return { items: [], nextCursor: null, error: `Request failed (${res.status})`, isNotFound: false };
    }
    return {
      items: (json.data ?? []) as T[],
      nextCursor: json.meta?.pagination?.next_cursor ?? null,
      error: null,
      isNotFound: false,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    return { items: [], nextCursor: null, error: message, isNotFound: false };
  }
}

// ---------------------------------------------------------------------------
// Financial data
// ---------------------------------------------------------------------------

export async function getFinancials(
  companyNumber: string,
  numPeriods = 5,
): Promise<FetchResult<FinancialsResponse>> {
  return apiFetch<FinancialsResponse>(
    `/api/v1/companies/${companyNumber}/financials?num_periods=${numPeriods}`,
  );
}

// ---------------------------------------------------------------------------
// Filings
// ---------------------------------------------------------------------------

export async function getFilings(
  companyNumber: string,
  options: { cursor?: string; limit?: number; category?: string } = {},
): Promise<ListFetchResult<FilingItem>> {
  const params = new URLSearchParams();
  if (options.cursor) params.set("cursor", options.cursor);
  if (options.limit) params.set("limit", String(options.limit));
  if (options.category) params.set("category", options.category);
  const qs = params.toString();
  return apiFetchList<FilingItem>(
    `/api/v1/companies/${companyNumber}/filings${qs ? `?${qs}` : ""}`,
  );
}

// ---------------------------------------------------------------------------
// Officers
// ---------------------------------------------------------------------------

export async function getOfficers(
  companyNumber: string,
  options: { status?: string } = {},
): Promise<ListFetchResult<OfficerItem>> {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  const qs = params.toString();
  return apiFetchList<OfficerItem>(
    `/api/v1/companies/${companyNumber}/officers${qs ? `?${qs}` : ""}`,
  );
}

// ---------------------------------------------------------------------------
// PSC
// ---------------------------------------------------------------------------

export async function getPsc(
  companyNumber: string,
  options: { status?: string } = {},
): Promise<ListFetchResult<PscItem>> {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  const qs = params.toString();
  return apiFetchList<PscItem>(
    `/api/v1/companies/${companyNumber}/psc${qs ? `?${qs}` : ""}`,
  );
}

// ---------------------------------------------------------------------------
// Charges
// ---------------------------------------------------------------------------

export async function getCharges(
  companyNumber: string,
  options: { status?: string } = {},
): Promise<ListFetchResult<ChargeItem>> {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  const qs = params.toString();
  return apiFetchList<ChargeItem>(
    `/api/v1/companies/${companyNumber}/charges${qs ? `?${qs}` : ""}`,
  );
}

// ---------------------------------------------------------------------------
// Watchlists (authenticated — pass authHeaders from getAuthHeader())
// ---------------------------------------------------------------------------

export async function getWatchlists(
  authHeaders: Record<string, string>,
): Promise<FetchResult<WatchlistOut[]>> {
  return apiFetch<WatchlistOut[]>("/api/v1/watchlists", {
    headers: authHeaders,
  });
}

export async function getWatchlistItems(
  watchlistId: string,
  authHeaders: Record<string, string>,
): Promise<FetchResult<{ watchlist: WatchlistOut; items: WatchlistItemOut[] }>> {
  return apiFetch(`/api/v1/watchlists/${watchlistId}`, {
    headers: authHeaders,
  });
}
