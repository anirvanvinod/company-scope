/**
 * SkeletonBlock — animate-pulse placeholder for loading states.
 */

import { cn } from "@/lib/utils";

interface SkeletonBlockProps {
  className?: string;
}

export function SkeletonBlock({ className }: SkeletonBlockProps) {
  return (
    <div
      className={cn("animate-pulse rounded bg-stone-200", className)}
      aria-hidden="true"
    />
  );
}
