/**
 * ConfidencePip — four-dot extraction-quality indicator.
 *
 * Communicates data extraction confidence, NOT company quality.
 * Displayed alongside any metric derived from filed accounts.
 *
 * Bands:
 *   high        ●●●●  strong structured evidence (iXBRL)
 *   medium      ●●●○  credible with interpretation
 *   low         ●●○○  ambiguous or partial data
 *   unavailable ○○○○  insufficient evidence or not attempted
 */

import { cn } from "@/lib/utils";
import type { ConfidenceBand } from "@/lib/types";

interface ConfidencePipProps {
  band: ConfidenceBand | string;
  /** Show the band label as text after the dots */
  label?: boolean;
  className?: string;
}

const BAND: Record<
  string,
  { filled: number; filledClass: string; labelText: string; labelClass: string }
> = {
  high: {
    filled: 4,
    filledClass: "bg-emerald-500",
    labelText: "High confidence",
    labelClass: "text-emerald-700",
  },
  medium: {
    filled: 3,
    filledClass: "bg-amber-500",
    labelText: "Medium confidence",
    labelClass: "text-amber-700",
  },
  low: {
    filled: 2,
    filledClass: "bg-stone-400",
    labelText: "Low confidence",
    labelClass: "text-stone-500",
  },
  unavailable: {
    filled: 0,
    filledClass: "bg-stone-300",
    labelText: "Confidence unavailable",
    labelClass: "text-stone-400",
  },
};

export function ConfidencePip({ band, label = false, className }: ConfidencePipProps) {
  const config = BAND[band] ?? BAND.unavailable;
  const title = `Extraction quality: ${config.labelText}. These indicators show how reliably the data was extracted from source filings — not a measure of company quality.`;

  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      title={title}
      aria-label={title}
    >
      <span className="inline-flex gap-0.5" aria-hidden="true" role="presentation">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn(
              "inline-block h-[6px] w-[6px] rounded-full",
              i < config.filled ? config.filledClass : "bg-stone-200",
            )}
          />
        ))}
      </span>
      {label && (
        <span className={cn("text-xs", config.labelClass)}>
          {config.labelText}
        </span>
      )}
    </span>
  );
}
