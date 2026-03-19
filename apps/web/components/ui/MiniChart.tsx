/**
 * MiniChart — pure server-rendered SVG line chart for financial time series.
 *
 * Design:
 *   - No charting library; safe to import in server components
 *   - Null values break the line rather than drawing to zero
 *   - Point color reflects confidence band (emerald=high, amber=medium, stone=low)
 *   - Y-axis shows abbreviated labels (£1.2M, £250K)
 *   - Accessible: role="img" with aria-label
 */

import { formatYAxisLabel } from "@/lib/utils";
import type { SeriesPoint, ConfidenceBand } from "@/lib/types";

interface MiniChartProps {
  points: SeriesPoint[];
  currency?: string | null;
  height?: number;
  label: string;
}

const POINT_COLORS: Record<ConfidenceBand, string> = {
  high: "#10b981",     // emerald-500
  medium: "#f59e0b",   // amber-500
  low: "#a8a29e",      // stone-400
  unavailable: "#d6d3d1", // stone-300
};

const LINE_COLOR = "#a8a29e"; // stone-400

export function MiniChart({ points, currency, height = 80, label }: MiniChartProps) {
  // Filter to points with numeric values
  const numeric = points.map((p) => ({
    ...p,
    num: p.value !== null ? parseFloat(p.value) : null,
  }));

  const values = numeric.map((p) => p.num).filter((v): v is number => v !== null);
  if (values.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-xs text-stone-400 italic"
        style={{ height }}
        role="img"
        aria-label={`${label}: insufficient data for chart`}
      >
        Insufficient data
      </div>
    );
  }

  const W = 300;
  const H = height;
  const PAD_LEFT = 44;
  const PAD_RIGHT = 8;
  const PAD_TOP = 8;
  const PAD_BOTTOM = 20;

  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const n = numeric.length;
  const xStep = (W - PAD_LEFT - PAD_RIGHT) / Math.max(n - 1, 1);

  function xAt(i: number) {
    return PAD_LEFT + i * xStep;
  }
  function yAt(v: number) {
    return PAD_TOP + (H - PAD_TOP - PAD_BOTTOM) * (1 - (v - minVal) / range);
  }

  // Build polyline segments (break on null values)
  const segments: string[][] = [];
  let current: string[] = [];
  for (let i = 0; i < numeric.length; i++) {
    const p = numeric[i];
    if (p.num === null) {
      if (current.length > 1) segments.push(current);
      current = [];
    } else {
      current.push(`${xAt(i).toFixed(1)},${yAt(p.num).toFixed(1)}`);
    }
  }
  if (current.length > 1) segments.push(current);

  // Y-axis labels (3 ticks)
  const yTicks = [minVal, minVal + range / 2, maxVal];

  // X-axis labels: show year from period_end
  const xLabels = numeric.map((p, i) => ({
    i,
    label: p.period_end ? p.period_end.slice(0, 4) : "",
  }));

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      height={H}
      role="img"
      aria-label={label}
      className="overflow-visible"
    >
      {/* Y-axis gridlines + labels */}
      {yTicks.map((tick, ti) => {
        const y = yAt(tick).toFixed(1);
        return (
          <g key={ti}>
            <line
              x1={PAD_LEFT}
              y1={y}
              x2={W - PAD_RIGHT}
              y2={y}
              stroke="#e7e5e4"
              strokeWidth="1"
            />
            <text
              x={PAD_LEFT - 4}
              y={y}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize="9"
              fill="#a8a29e"
            >
              {formatYAxisLabel(tick, currency)}
            </text>
          </g>
        );
      })}

      {/* Line segments */}
      {segments.map((seg, si) => (
        <polyline
          key={si}
          points={seg.join(" ")}
          fill="none"
          stroke={LINE_COLOR}
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      ))}

      {/* Data points */}
      {numeric.map((p, i) => {
        if (p.num === null) return null;
        const band: ConfidenceBand = (p.confidence_band in POINT_COLORS)
          ? (p.confidence_band as ConfidenceBand)
          : "unavailable";
        return (
          <circle
            key={i}
            cx={xAt(i).toFixed(1)}
            cy={yAt(p.num).toFixed(1)}
            r="3"
            fill={POINT_COLORS[band]}
            stroke="white"
            strokeWidth="1"
          >
            <title>{`${p.period_end}: ${formatYAxisLabel(p.num, currency)}`}</title>
          </circle>
        );
      })}

      {/* X-axis labels */}
      {xLabels.map(({ i, label: xl }) => (
        <text
          key={i}
          x={xAt(i).toFixed(1)}
          y={H - 4}
          textAnchor="middle"
          fontSize="9"
          fill="#a8a29e"
        >
          {xl}
        </text>
      ))}
    </svg>
  );
}
