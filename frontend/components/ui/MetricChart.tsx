"use client";

import { useMemo } from "react";

const WIDTH = 640;
const ROW_HEIGHT = 30;
const LABEL_WIDTH = 200;
const VALUE_WIDTH = 90;

function truncate(value: string, max = 28): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

/**
 * Horizontal bar chart for experiment metrics. Only numeric metrics are
 * plotted; the raw values stay available in the metrics table.
 */
export function MetricChart({
  metrics,
}: {
  metrics: Record<string, unknown>;
}) {
  const entries = useMemo(
    () =>
      Object.entries(metrics)
        .map(([name, value]) => ({ name, value: toNumber(value) }))
        .filter((entry): entry is { name: string; value: number } => entry.value !== null),
    [metrics],
  );

  if (entries.length === 0) return null;

  const max = Math.max(...entries.map((entry) => Math.abs(entry.value)), 1);
  const barWidth = WIDTH - LABEL_WIDTH - VALUE_WIDTH;
  const height = entries.length * ROW_HEIGHT + 12;

  return (
    <svg
      className="chart"
      viewBox={`0 0 ${WIDTH} ${height}`}
      role="img"
      aria-label="Experiment metrics"
      preserveAspectRatio="xMinYMin meet"
    >
      {entries.map((entry, index) => {
        const y = index * ROW_HEIGHT + 6;
        const width = Math.max((Math.abs(entry.value) / max) * barWidth, 2);
        return (
          <g key={entry.name}>
            <text className="chart-label" x={0} y={y + 13}>
              {truncate(entry.name)}
            </text>
            <rect
              x={LABEL_WIDTH}
              y={y + 3}
              width={barWidth}
              height={14}
              rx={3}
              fill="var(--surface-3)"
            />
            <rect
              x={LABEL_WIDTH}
              y={y + 3}
              width={width}
              height={14}
              rx={3}
              fill="var(--accent)"
              opacity={0.85}
            />
            <text className="chart-value" x={WIDTH} y={y + 13} textAnchor="end">
              {entry.value}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
