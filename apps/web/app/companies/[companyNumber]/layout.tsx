/**
 * Company route layout — thin wrapper only.
 *
 * The company header and tab navigation live in page.tsx so they render
 * in the correct visual order (header → tabs → content). When Phase 7B.2
 * adds sub-page routes, each sub-page includes the tab nav inline, which
 * allows Next.js fetch deduplication to avoid redundant API calls.
 */

export default function CompanyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="flex flex-1 flex-col">{children}</div>;
}
