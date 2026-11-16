"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardSummary } from "@/lib/dashboard/metrics";
import { useI18n } from "@/lib/i18n/provider";

import { LazyStripChart } from "./lazy-charts";
import { SectionError } from "./section-error";

const PERIODS = [7, 30, 90] as const;
export type DashboardPeriod = (typeof PERIODS)[number];

export type RiskDistributionProps = {
  summary: DashboardSummary | null;
  period: DashboardPeriod;
  onPeriodChange: (period: DashboardPeriod) => void;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  truncated: boolean;
};

export function RiskDistribution({
  summary,
  period,
  onPeriodChange,
  loading,
  error,
  onRetry,
  truncated,
}: RiskDistributionProps) {
  const { t } = useI18n();
  const hasCompleted = summary !== null && summary.currentCompleted.length > 0;

  return (
    <section aria-labelledby="dashboard-distribution-title" className="min-w-0">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2
              id="dashboard-distribution-title"
              className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
            >
              {t("dashboard.chart.title")}
            </h2>
            {truncated ? <Badge variant="outline">{t("dashboard.sampleBadge")}</Badge> : null}
          </div>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
            {t("dashboard.chart.description")}
          </p>
        </div>

        <div
          role="group"
          aria-label={t("dashboard.chart.period")}
          className="flex items-center gap-1"
        >
          {PERIODS.map((days) => (
            <Button
              key={days}
              type="button"
              size="sm"
              variant={period === days ? "default" : "outline"}
              aria-pressed={period === days}
              onClick={() => onPeriodChange(days)}
            >
              {t("dashboard.chart.days", { days })}
            </Button>
          ))}
        </div>
      </div>

      <div className="mt-5 rounded-[6px] border border-border bg-card p-4 sm:p-5">
        {loading ? (
          <div className="space-y-3" role="status" aria-live="polite">
            <span className="sr-only">{t("dashboard.loading")}</span>
            <div className="flex gap-1">
              {Array.from({ length: 18 }).map((_, index) => (
                <Skeleton
                  key={index}
                  className="w-full"
                  style={{ height: `${24 + ((index * 13) % 72)}px` }}
                />
              ))}
            </div>
            <Skeleton className="h-3 w-full" />
          </div>
        ) : error ? (
          <SectionError onRetry={onRetry} />
        ) : hasCompleted && summary ? (
          <div>
            <LazyStripChart
              data={summary.strip}
              height={200}
              showTotals={false}
              ariaLabel={t("dashboard.chart.aria", { days: period })}
              className={period > 7 ? "[&>div:nth-child(3)]:hidden" : undefined}
            />
            {period > 7 ? (
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                {t("dashboard.chart.dayCaption")}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="flex min-h-[200px] flex-col items-start justify-center gap-2">
            <p className="font-serif text-2xl leading-tight tracking-tight">
              {t("dashboard.chart.emptyTitle")}
            </p>
            <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
              {t("dashboard.chart.emptyDescription")}
            </p>
            <Button asChild variant="outline" size="sm" className="mt-2">
              <Link href="/verificacao">{t("dashboard.actions.openVerification")}</Link>
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
