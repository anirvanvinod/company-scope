import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string | null;
  className?: string;
}

const STYLES: Record<string, string> = {
  active: "text-emerald-700 bg-emerald-50 ring-emerald-200",
  dissolved: "text-stone-500 bg-stone-100 ring-stone-200",
  liquidation: "text-red-700 bg-red-50 ring-red-200",
  receivership: "text-red-700 bg-red-50 ring-red-200",
  administration: "text-amber-700 bg-amber-50 ring-amber-200",
  "voluntary-arrangement": "text-amber-700 bg-amber-50 ring-amber-200",
  "insolvency-proceedings": "text-red-700 bg-red-50 ring-red-200",
  "converted-closed": "text-stone-500 bg-stone-100 ring-stone-200",
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const key = status?.toLowerCase() ?? "";
  const styles = STYLES[key] ?? "text-stone-500 bg-stone-100 ring-stone-200";
  const label = status
    ? status.charAt(0).toUpperCase() + status.slice(1).replace(/-/g, " ")
    : "Unknown";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        styles,
        className,
      )}
    >
      {label}
    </span>
  );
}
