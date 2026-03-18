"use client";

/**
 * CompanyTabNav — tab strip for the company detail page.
 *
 * Client component so it can read usePathname() to highlight the active tab.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { label: "Overview", href: "" },
  { label: "Financials", href: "/financials" },
  { label: "Filings", href: "/filings" },
  { label: "Officers", href: "/officers" },
  { label: "Ownership", href: "/ownership" },
  { label: "Charges", href: "/charges" },
] as const;

interface CompanyTabNavProps {
  base: string;
}

export function CompanyTabNav({ base }: CompanyTabNavProps) {
  const pathname = usePathname();

  return (
    <div className="-mb-px flex overflow-x-auto">
      {TABS.map((tab) => {
        const href = `${base}${tab.href}`;
        const isActive =
          tab.href === ""
            ? pathname === base || pathname === `${base}/`
            : pathname.startsWith(href);

        return (
          <Link
            key={tab.label}
            href={href}
            className={cn(
              "flex-shrink-0 border-b-2 px-4 py-3 text-sm transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500",
              isActive
                ? "border-stone-900 font-medium text-stone-900"
                : "border-transparent text-stone-500 hover:border-stone-300 hover:text-stone-700",
            )}
            aria-current={isActive ? "page" : undefined}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
