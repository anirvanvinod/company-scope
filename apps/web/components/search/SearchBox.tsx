"use client";

/**
 * SearchBox — the primary search input.
 *
 * Client component: uses useRouter so the submission triggers a client-side
 * navigation, which avoids a full page reload on the home page.
 *
 * Falls back gracefully: if JS is disabled the enclosing <form> with
 * action="/search" still navigates correctly (progressive enhancement).
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface SearchBoxProps {
  defaultValue?: string;
  size?: "default" | "large";
  placeholder?: string;
  autoFocus?: boolean;
}

export function SearchBox({
  defaultValue = "",
  size = "default",
  placeholder = "Search by company name or number…",
  autoFocus = false,
}: SearchBoxProps) {
  const [value, setValue] = useState(defaultValue);
  const router = useRouter();
  const isLarge = size === "large";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  return (
    <form onSubmit={handleSubmit} action="/search" method="GET" className="w-full">
      <div className="relative flex w-full overflow-hidden rounded-lg border border-stone-300 bg-white shadow-sm focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100">
        <label
          htmlFor="hero-search"
          className="sr-only"
        >
          {placeholder}
        </label>
        <input
          id="hero-search"
          type="search"
          name="q"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          autoFocus={autoFocus}
          autoComplete="off"
          className={cn(
            "flex-1 bg-transparent text-stone-900 placeholder-stone-400 focus:outline-none",
            isLarge ? "px-5 py-4 text-base" : "px-4 py-2.5 text-sm",
          )}
          aria-label={placeholder}
        />
        <button
          type="submit"
          className={cn(
            "flex-shrink-0 bg-blue-700 text-white hover:bg-blue-800 active:bg-blue-900",
            "transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1",
            isLarge ? "px-6 py-4" : "px-4 py-2.5",
          )}
          aria-label="Search"
        >
          <SearchIcon size={isLarge ? 18 : 15} />
        </button>
      </div>
    </form>
  );
}

function SearchIcon({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M10.5 10.5L13 13"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
