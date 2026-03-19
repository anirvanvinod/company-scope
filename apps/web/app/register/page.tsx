/**
 * Registration page — /register
 *
 * Server Action (signUp) creates the account and sets the session cookie.
 * Redirects to /watchlists on success.
 */

"use client";

import { useActionState } from "react";
import Link from "next/link";

import { signUp } from "@/lib/auth";

export default function RegisterPage() {
  const [state, action, isPending] = useActionState(signUp, { error: null });

  return (
    <main className="mx-auto max-w-sm px-4 py-16">
      <h1 className="mb-8 text-xl font-semibold text-stone-900">Create account</h1>

      <form action={action} className="space-y-4">
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
            htmlFor="display_name"
            className="mb-1 block text-xs font-medium text-stone-700"
          >
            Name{" "}
            <span className="font-normal text-stone-400">(optional)</span>
          </label>
          <input
            id="display_name"
            name="display_name"
            type="text"
            autoComplete="name"
            className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <div>
          <label
            htmlFor="password"
            className="mb-1 block text-xs font-medium text-stone-700"
          >
            Password{" "}
            <span className="font-normal text-stone-400">(8 characters minimum)</span>
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm text-stone-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <button
          type="submit"
          disabled={isPending}
          className="w-full rounded-md bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-60"
        >
          {isPending ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="mt-6 text-center text-xs text-stone-400">
        Already have an account?{" "}
        <Link href="/sign-in" className="text-stone-600 underline-offset-2 hover:underline">
          Sign in
        </Link>
      </p>

      <p className="mt-4 text-center text-xs text-stone-300">
        CompanyScope uses public data only. No financial advice is provided.
      </p>
    </main>
  );
}
