import { cn, formatRelativeTime } from "@/lib/utils";

interface FreshnessTagProps {
  lastCheckedAt: string | null;
  freshnessStatus?: string;
  className?: string;
}

export function FreshnessTag({
  lastCheckedAt,
  freshnessStatus,
  className,
}: FreshnessTagProps) {
  const relative = formatRelativeTime(lastCheckedAt);
  const isStale = freshnessStatus === "stale";

  return (
    <span className={cn("inline-flex items-center gap-1 text-xs", className)}>
      {/* Clock icon */}
      <svg
        width="12"
        height="12"
        viewBox="0 0 16 16"
        fill="none"
        aria-hidden="true"
        className={isStale ? "text-amber-500" : "text-stone-400"}
      >
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M8 4.5V8l2.5 2"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
      {relative ? (
        <>
          <span className={isStale ? "text-amber-600" : "text-stone-500"}>
            Updated {relative}
          </span>
          {isStale && (
            <span className="font-medium text-amber-600">· Stale</span>
          )}
        </>
      ) : (
        <span className="text-stone-400">Source date unknown</span>
      )}
    </span>
  );
}
