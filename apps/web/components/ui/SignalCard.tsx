/**
 * SignalCard — displays a rule-based risk signal with severity indicator.
 *
 * Design rules (per docs/11-ui-ux-principles.md):
 *   - Severity expressed as a badge + border tint, not full background fill
 *   - No alarmist language — show explanation as written by the methodology
 *   - "compact" variant for the alert strip; default for signal list pages
 */

import { cn } from "@/lib/utils";
import type { ActiveSignalSummary, SignalSeverity } from "@/lib/types";

const SEVERITY: Record<
  SignalSeverity,
  { wrapper: string; badge: string }
> = {
  high: {
    wrapper: "border-red-200 bg-red-50/60",
    badge: "text-red-700 bg-red-100 ring-red-200",
  },
  medium: {
    wrapper: "border-amber-200 bg-amber-50/60",
    badge: "text-amber-700 bg-amber-100 ring-amber-200",
  },
  low: {
    wrapper: "border-blue-200 bg-blue-50/60",
    badge: "text-blue-700 bg-blue-100 ring-blue-200",
  },
  info: {
    wrapper: "border-stone-200 bg-stone-50",
    badge: "text-stone-600 bg-stone-100 ring-stone-200",
  },
};

interface SignalCardProps {
  signal: Pick<
    ActiveSignalSummary,
    "signal_code" | "signal_name" | "category" | "severity" | "explanation"
  >;
  /** Compact inline pill for the alert strip */
  compact?: boolean;
  className?: string;
}

export function SignalCard({ signal, compact = false, className }: SignalCardProps) {
  const sev: SignalSeverity = signal.severity in SEVERITY
    ? (signal.severity as SignalSeverity)
    : "info";
  const styles = SEVERITY[sev];

  if (compact) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-md border px-3 py-2",
          styles.wrapper,
          className,
        )}
      >
        <SeverityBadge severity={sev} styles={styles.badge} />
        <span className="text-sm text-stone-800">{signal.signal_name}</span>
      </div>
    );
  }

  return (
    <div className={cn("rounded-lg border p-4", styles.wrapper, className)}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <SeverityBadge severity={sev} styles={styles.badge} />
            <span className="text-sm font-medium text-stone-900">
              {signal.signal_name}
            </span>
            <span className="ml-auto text-xs text-stone-400">
              {signal.category}
            </span>
          </div>
          <p className="text-sm leading-relaxed text-stone-700">
            {signal.explanation}
          </p>
        </div>
      </div>
    </div>
  );
}

function SeverityBadge({
  severity,
  styles,
}: {
  severity: string;
  styles: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1 ring-inset",
        styles,
      )}
    >
      {severity}
    </span>
  );
}
