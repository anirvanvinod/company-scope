/**
 * NullState — explicit display for missing, unavailable, or unextracted data.
 *
 * Never shows a bare dash. Always gives the user a reason.
 *
 * Variants:
 *   inline — muted italic text, for use within a table cell or inline context
 *   block  — bordered box, for use when a whole section has no data
 */

import { cn } from "@/lib/utils";

interface NullStateProps {
  /** Human-readable explanation of why the data is absent */
  reason?: string;
  /** Render as inline text rather than a block card */
  inline?: boolean;
  className?: string;
}

const DEFAULT_REASON = "Not available in source data";

export function NullState({
  reason = DEFAULT_REASON,
  inline = false,
  className,
}: NullStateProps) {
  if (inline) {
    return (
      <span
        className={cn("text-sm italic text-stone-400", className)}
        title={reason}
      >
        Not available
      </span>
    );
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-stone-200 bg-stone-50 px-4 py-5 text-center",
        className,
      )}
    >
      <p className="text-sm leading-relaxed text-stone-500">{reason}</p>
    </div>
  );
}
