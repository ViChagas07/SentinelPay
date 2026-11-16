"use client";

import { RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Payable } from "@/lib/api/schemas";
import {
  buildPendingReceiptSeries,
  countPendingConfirmations,
  formatBoundedCount,
  type DashboardSummary,
} from "@/lib/dashboard/metrics";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { LazySparkline } from "./lazy-charts";

const PENDING_SERIES_DAYS = 14;

type MetricRowProps = {
  label: string;
  value: string | null;
  hint?: string;
  sparkline?: readonly number[];
  sparklineLabel?: string;
  loading?: boolean;
  onRetry?: () => void;
  sparklineClassName?: string;
};

function MetricRow({
  label,
  value,
  hint,
  sparkline,
  sparklineLabel,
  loading = false,
  onRetry,
  sparklineClassName = "text-primary",
}: MetricRowProps) {
  const { t } = useI18n();

  return (
    <div className="flex min-w-0 items-center justify-between gap-4 border-b border-border py-3 last:border-b-0">
      <div className="min-w-0">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
          {label}
        </p>
        <div className="mt-1 flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
          {loading ? (
            <Skeleton className="h-7 w-14" />
          ) : value !== null ? (
            <span className="font-mono text-2xl leading-none tabular-nums">{value}</span>
          ) : (
            <span className="text-sm font-medium text-muted-foreground">
              {t("dashboard.metrics.unavailable")}
            </span>
          )}
          {hint ? (
            <span className="min-w-0 truncate text-xs text-muted-foreground">{hint}</span>
          ) : null}
        </div>
      </div>

      {loading ? (
        <Skeleton className="h-7 w-24 shrink-0" />
      ) : sparkline && sparkline.length > 0 ? (
        <LazySparkline
          data={sparkline}
          width={100}
          height={28}
          ariaLabel={sparklineLabel}
          className={cn("shrink-0", sparklineClassName)}
        />
      ) : onRetry ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onRetry}
          aria-label={t("dashboard.error.retry")}
        >
          <RefreshCw aria-hidden="true" />
        </Button>
      ) : null}
    </div>
  );
}

export type SecondaryMetricsProps = {
  summary: DashboardSummary | null;
  period: number;
  analysesLoading: boolean;
  analysesError: boolean;
  onRetryAnalyses: () => void;
  payables: readonly Payable[] | null;
  payablesTruncated: boolean;
  payablesLoading: boolean;
  payablesError: boolean;
  onRetryPayables: () => void;
  timeZone: string;
  now: Date;
  truncated: boolean;
};

export function SecondaryMetrics({
  summary,
  period,
  analysesLoading,
  analysesError,
  onRetryAnalyses,
  payables,
  payablesTruncated,
  payablesLoading,
  payablesError,
  onRetryPayables,
  timeZone,
  now,
  truncated,
}: SecondaryMetricsProps) {
  const { t } = useI18n();
  const pendingCount = payables ? countPendingConfirmations(payables) : null;
  const pendingValue =
    pendingCount === null
      ? null
      : payablesTruncated
        ? pendingCount > 0
          ? formatBoundedCount(pendingCount, true)
          : null
        : String(pendingCount);
  const pendingSeries = payables
    ? buildPendingReceiptSeries(payables, PENDING_SERIES_DAYS, now, timeZone)
    : [];
  const analyzedValue = summary ? formatBoundedCount(summary.analyzedCount, truncated) : null;
  const highRiskValue = summary ? formatBoundedCount(summary.highRiskCount, truncated) : null;

  return (
    <section aria-labelledby="dashboard-metrics-title" className="min-w-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2
          id="dashboard-metrics-title"
          className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground"
        >
          {t("dashboard.metrics.title")}
        </h2>
        <div className="flex items-center gap-2">
          {truncated ? <Badge variant="outline">{t("dashboard.sampleBadge")}</Badge> : null}
          <p className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
            {t("dashboard.period.current", { days: period })}
          </p>
        </div>
      </div>

      <div className="mt-3 border-t border-border">
        <MetricRow
          label={t("dashboard.metrics.analyzed")}
          value={analyzedValue}
          hint={t("dashboard.metrics.periodHint")}
          sparkline={summary?.documentsSeries}
          sparklineLabel={t("dashboard.metrics.analyzedSparkline")}
          loading={analysesLoading}
          onRetry={analysesError ? onRetryAnalyses : undefined}
        />
        <MetricRow
          label={t("dashboard.metrics.highRisk")}
          value={highRiskValue}
          hint={t("dashboard.metrics.highRiskHint")}
          sparkline={summary?.highRiskSeries}
          sparklineLabel={t("dashboard.metrics.highRiskSparkline")}
          loading={analysesLoading}
          onRetry={analysesError ? onRetryAnalyses : undefined}
          sparklineClassName="text-risk-high"
        />
        <MetricRow
          label={t("dashboard.metrics.pendingReceipts")}
          value={pendingValue}
          hint={t("dashboard.metrics.pendingHint")}
          sparkline={pendingSeries}
          sparklineLabel={t("dashboard.metrics.pendingSparkline")}
          loading={payablesLoading}
          onRetry={payablesError ? onRetryPayables : undefined}
        />
      </div>
    </section>
  );
}
