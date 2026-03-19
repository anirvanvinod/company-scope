/**
 * Loading skeleton for all /companies/[companyNumber]/* routes.
 * Shown while the layout or any sub-page is fetching data.
 */

import { SkeletonBlock } from "@/components/ui/SkeletonBlock";

export default function CompanyLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column */}
        <div className="space-y-6 lg:col-span-2">
          <div className="rounded-lg border border-stone-200 bg-white p-5">
            <SkeletonBlock className="mb-4 h-4 w-32" />
            <div className="grid grid-cols-2 gap-4">
              <SkeletonBlock className="h-10" />
              <SkeletonBlock className="h-10" />
              <SkeletonBlock className="h-10" />
              <SkeletonBlock className="h-10" />
            </div>
          </div>
          <div className="rounded-lg border border-stone-200 bg-white p-5">
            <SkeletonBlock className="mb-4 h-4 w-24" />
            <SkeletonBlock className="mb-2 h-3 w-full" />
            <SkeletonBlock className="mb-2 h-3 w-5/6" />
            <SkeletonBlock className="h-3 w-4/5" />
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          <div className="rounded-lg border border-stone-200 bg-white p-4">
            <SkeletonBlock className="mb-3 h-4 w-28" />
            <SkeletonBlock className="mb-2 h-8" />
            <SkeletonBlock className="h-8" />
          </div>
          <div className="rounded-lg border border-stone-200 bg-white p-4">
            <SkeletonBlock className="mb-3 h-4 w-24" />
            <SkeletonBlock className="mb-2 h-8" />
            <SkeletonBlock className="h-8" />
          </div>
        </div>
      </div>
    </div>
  );
}
