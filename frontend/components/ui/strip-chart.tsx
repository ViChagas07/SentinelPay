"use client";

import { useI18n } from "@/lib/i18n/provider";
import { getRiskPresentation } from "@/lib/risk/presentation";
import { RISK_BAND_LAYOUT } from "@/lib/risk/ruler";
import { cn } from "@/lib/utils";

export type StripChartPoint = {
  date: string;
  low: number;
  attention: number;
  high: number;
};

export type StripChartProps = {
  data: readonly StripChartPoint[];
  height?: number;
  showTotals?: boolean;
  ariaLabel?: string;
  className?: string;
};

function totalOf(point: StripChartPoint): number {
  return point.low + point.attention + point.high;
}

export function StripChart({
  data,
  height = 160,
  showTotals = true,
  ariaLabel,
  className,
}: StripChartProps) {
  const { t, formatDate } = useI18n();
  const count = data.length;
  const maxTotal = Math.max(1, ...data.map(totalOf));
  const barSlot = count > 0 ? 100 / count : 100;
  const barGap = barSlot * 0.2;
  const barWidth = Math.max(0, barSlot - barGap * 2);

  return (
    <div className={cn("w-full min-w-0", className)}>
      <div
        className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground"
        aria-hidden="true"
      >
        {RISK_BAND_LAYOUT.map((band) => {
          const presentation = getRiskPresentation(band.band);

          return (
            <span key={band.band} className="inline-flex items-center gap-1.5">
              <span className="h-px w-3" style={{ backgroundColor: presentation.color }} />
              {t(presentation.labelKey)}
            </span>
          );
        })}
      </div>
      <div className="relative mt-3 w-full" style={{ height }}>
        <svg
          role="img"
          aria-label={ariaLabel ?? t("design.chart.strip.aria")}
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full"
          fill="none"
        >
          {[0, 50, 100].map((line) => (
            <line
              key={line}
              x1={0}
              y1={line}
              x2={100}
              y2={line}
              stroke="var(--border)"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {data.map((point, index) => {
            const lowHeight = (point.low / maxTotal) * 100;
            const attentionHeight = (point.attention / maxTotal) * 100;
            const highHeight = (point.high / maxTotal) * 100;
            const x = index * barSlot + barGap;
            const lowY = 100 - lowHeight;
            const attentionY = lowY - attentionHeight;
            const highY = attentionY - highHeight;

            return (
              <g key={point.date} aria-hidden="true">
                <rect
                  x={x}
                  y={lowY}
                  width={barWidth}
                  height={lowHeight}
                  fill="var(--risk-low)"
                  stroke="var(--surface)"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
                <rect
                  x={x}
                  y={attentionY}
                  width={barWidth}
                  height={attentionHeight}
                  fill="var(--risk-medium)"
                  stroke="var(--surface)"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
                <rect
                  x={x}
                  y={highY}
                  width={barWidth}
                  height={highHeight}
                  fill="var(--risk-high)"
                  stroke="var(--surface)"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
              </g>
            );
          })}
        </svg>
        {showTotals ? (
          <div className="pointer-events-none absolute inset-0" aria-hidden="true">
            {data.map((point, index) => {
              const total = totalOf(point);

              return (
                <span
                  key={point.date}
                  className="absolute -translate-x-1/2 -translate-y-full font-mono text-[0.6rem] tabular-nums text-muted-foreground"
                  style={{
                    left: `${((index + 0.5) / count) * 100}%`,
                    bottom: `${(total / maxTotal) * 100}%`,
                  }}
                >
                  {total}
                </span>
              );
            })}
          </div>
        ) : null}
      </div>
      <div
        className="mt-2 grid gap-1"
        style={{ gridTemplateColumns: `repeat(${Math.max(count, 1)}, minmax(0, 1fr))` }}
        aria-hidden="true"
      >
        {data.map((point) => (
          <span
            key={point.date}
            className="truncate text-center font-mono text-[0.6rem] text-muted-foreground"
          >
            {formatDate(point.date, { weekday: "short" })}
          </span>
        ))}
      </div>
      <div className="sr-only">
        <table>
          <caption>{ariaLabel ?? t("design.chart.strip.aria")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("design.chart.date")}</th>
              {RISK_BAND_LAYOUT.map((band) => (
                <th key={band.band} scope="col">
                  {t(getRiskPresentation(band.band).labelKey)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((point) => (
              <tr key={point.date}>
                <th scope="row">{formatDate(point.date, { weekday: "short" })}</th>
                <td>{point.low}</td>
                <td>{point.attention}</td>
                <td>{point.high}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
