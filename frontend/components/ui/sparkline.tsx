"use client";

import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export type SparklineProps = {
  data: readonly number[];
  width?: number;
  height?: number;
  ariaLabel?: string;
  className?: string;
};

function buildPoints(data: readonly number[], width: number, height: number): string {
  if (data.length === 0) {
    return "";
  }

  if (data.length === 1) {
    const middle = height / 2;
    return `0,${middle} ${width},${middle}`;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;

  return data
    .map((value, index) => {
      const x = (index / (data.length - 1)) * width;
      const y = height - ((value - min) / span) * height;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

export function Sparkline({
  data,
  width = 120,
  height = 32,
  ariaLabel,
  className,
}: SparklineProps) {
  const { t } = useI18n();

  if (data.length === 0) {
    return null;
  }

  return (
    <svg
      role="img"
      aria-label={ariaLabel ?? t("design.chart.sparkline.aria", { count: data.length })}
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      preserveAspectRatio="none"
      className={cn("overflow-visible", className)}
      fill="none"
    >
      <polyline
        points={buildPoints(data, width, height)}
        stroke="currentColor"
        strokeWidth={1}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
