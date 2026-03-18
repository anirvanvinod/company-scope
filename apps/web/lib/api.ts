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

import type { CompanyAggregate, SearchResultItem } from "./types";

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
