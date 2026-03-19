/**
 * Server-side session utilities and auth Server Actions.
 *
 * All functions in this file run on the Next.js server only.
 * They read/write the cs_session HTTP-only cookie via next/headers.
 *
 * The cookie value is a JWT produced by the FastAPI backend.
 * Next.js never exposes it to browser JavaScript.
 *
 * getServerSession / getAuthHeader — plain server utilities (no "use server")
 * signIn / signUp / signOut       — Server Actions (inline "use server" directive)
 */

import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { UserProfile } from "./types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function apiBase(): string {
  return (
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000"
  );
}

/**
 * Return the Authorization header value for the current session, or null.
 * Used by server components and server actions when calling authenticated
 * FastAPI endpoints.
 */
export async function getAuthHeader(): Promise<{ Authorization: string } | Record<string, never>> {
  const cookieStore = await cookies();
  const session = cookieStore.get("cs_session");
  if (!session) return {};
  return { Authorization: `Bearer ${session.value}` };
}

// ---------------------------------------------------------------------------
// Session reading
// ---------------------------------------------------------------------------

/**
 * Return the current user profile, or null if not signed in.
 *
 * Uses React cache() so multiple server components in the same render
 * tree share a single /api/v1/me request.
 */
export const getServerSession = cache(async (): Promise<UserProfile | null> => {
  const authHeader = await getAuthHeader();
  if (!("Authorization" in authHeader)) return null;

  try {
    const res = await fetch(`${apiBase()}/api/v1/me`, {
      cache: "no-store",
      headers: authHeader,
    });
    if (!res.ok) return null;
    const json = await res.json();
    return (json?.data as UserProfile) ?? null;
  } catch {
    return null;
  }
});

// ---------------------------------------------------------------------------
// Auth Server Actions
// ---------------------------------------------------------------------------

export async function signIn(
  _prevState: { error: string | null },
  formData: FormData,
): Promise<{ error: string | null }> {
  "use server";
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;
  const next = (formData.get("next") as string) || "/watchlists";

  try {
    const res = await fetch(`${apiBase()}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });

    const json = await res.json();

    if (!res.ok) {
      return { error: json.error?.message ?? "Sign in failed. Please try again." };
    }

    const token: string = json.data?.access_token;
    if (!token) return { error: "Unexpected response from server." };

    const cookieStore = await cookies();
    cookieStore.set("cs_session", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      maxAge: 30 * 24 * 60 * 60,
      path: "/",
    });
  } catch {
    return { error: "Could not connect to the server. Please try again." };
  }

  redirect(next);
}

export async function signUp(
  _prevState: { error: string | null },
  formData: FormData,
): Promise<{ error: string | null }> {
  "use server";
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;
  const displayName = (formData.get("display_name") as string) || undefined;

  try {
    const res = await fetch(`${apiBase()}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName }),
      cache: "no-store",
    });

    const json = await res.json();

    if (!res.ok) {
      return { error: json.error?.message ?? "Registration failed. Please try again." };
    }

    const token: string = json.data?.access_token;
    if (!token) return { error: "Unexpected response from server." };

    const cookieStore = await cookies();
    cookieStore.set("cs_session", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      maxAge: 30 * 24 * 60 * 60,
      path: "/",
    });
  } catch {
    return { error: "Could not connect to the server. Please try again." };
  }

  redirect("/watchlists");
}

export async function signOut(): Promise<void> {
  "use server";
  const cookieStore = await cookies();
  cookieStore.delete("cs_session");
  redirect("/");
}
