/**
 * Sign-in page — /sign-in
 *
 * Uses a Server Action (signIn from lib/auth.ts) so no client-side JS is
 * required for the form submission. After a successful login the server
 * action sets the cs_session cookie and redirects.
 */

"use client";

import { useActionState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { signIn } from "@/lib/auth";

export default function SignInPage() {
  return (
    <Suspense>
      <SignInForm />
    </Suspense>
  );
}

function SignInForm() {
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/watchlists";

  const [state, action, isPending] = useActionState(signIn, { error: null });

  return (
    <main className="mx-auto max-w-sm px-4 py-16">
      <h1 className="mb-8 text-xl font-semibold text-stone-900">Sign in</h1>

      <form action={action} className="space-y-4">
        <input type="hidden" name="next" value={next} />

        {state.error && (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {state.error}
          </p>
        )}

        <div>
          <label
            htmlFor="email"
            className="mb-1 block text-xs font-medium text-stone-700"
          >
            Email address
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="email"
            className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <div>
          <label
            htmlFor="password"
            className="mb-1 block text-xs font-medium text-stone-700"
          >
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            autoComplete="current-password"
            className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm text-stone-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <button
          type="submit"
          disabled={isPending}
          className="w-full rounded-md bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-60"
        >
          {isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="mt-6 text-center text-xs text-stone-400">
        No account?{" "}
        <Link href="/register" className="text-stone-600 underline-offset-2 hover:underline">
          Create one
        </Link>
      </p>
    </main>
  );
}
