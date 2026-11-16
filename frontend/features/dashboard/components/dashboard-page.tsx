"use client";

import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { useAnalyses } from "@/features/analyses/hooks/use-analyses";
import { useSession } from "@/features/auth/hooks/use-session";
import { usePayables } from "@/features/payables/hooks/use-payables";
import type { PayableStatus } from "@/lib/api/schemas";
import { formatDashboardDate, resolveTimeZone } from "@/lib/dashboard/date";
import { buildDashboardSummary } from "@/lib/dashboard/metrics";
import { useI18n } from "@/lib/i18n/provider";

import { useDashboardAnalyses } from "../hooks/use-dashboard-analyses";
import { DashboardPageSkeleton, RiskSummarySkeleton } from "./dashboard-skeletons";
import { RecentAnalyses } from "./recent-analyses";
import { RiskDistribution, type DashboardPeriod } from "./risk-distribution";
import { RiskSummary } from "./risk-summary";
import { SecondaryMetrics } from "./secondary-metrics";
import { SectionError } from "./section-error";
import { UpcomingPayables } from "./upcoming-payables";

const ACTIVE_PAYABLE_STATUSES: PayableStatus[] = ["pending_confirmation", "pending", "overdue"];
const DEFAULT_PERIOD: DashboardPeriod = 30;

export function DashboardPage() {
  const { t, locale } = useI18n();
  const { user, status } = useSession();
  const [period, setPeriod] = useState<DashboardPeriod>(DEFAULT_PERIOD);
  const analysesQuery = useDashboardAnalyses(period);
  const recentQuery = useAnalyses({ limit: 8, refetchOnWindowFocus: true });
  const payablesQuery = usePayables({
    status: ACTIVE_PAYABLE_STATUSES,
    limit: 50,
    refetchOnWindowFocus: true,
  });

  const now = new Date();
  const timeZone = resolveTimeZone(user?.timezone);
  const fetchedAt = analysesQuery.data?.fetchedAt;
  const summary = useMemo(() => {
    if (!analysesQuery.data || !fetchedAt) {
      return null;
    }

    return buildDashboardSummary(analysesQuery.data.items, period, new Date(fetchedAt), timeZone);
  }, [analysesQuery.data, fetchedAt, period, timeZone]);

  if (status !== "authenticated" || !user) {
    return <DashboardPageSkeleton />;
  }

  const recentItems = recentQuery.data?.items ?? [];
  const payables = payablesQuery.data?.items ?? [];
  const payablesTruncated = Boolean(payablesQuery.data?.next_cursor);
  const hasData = Boolean(analysesQuery.data || recentQuery.data || payablesQuery.data);
  const firstLoad =
    !hasData && (analysesQuery.isPending || recentQuery.isPending || payablesQuery.isPending);
  const isNewAccount =
    analysesQuery.isSuccess &&
    recentQuery.isSuccess &&
    payablesQuery.isSuccess &&
    recentItems.length === 0 &&
    payables.length === 0;
  const truncated = analysesQuery.data?.truncated ?? false;
  const name = user.name?.trim();
  const greeting = name ? t("dashboard.greeting", { name }) : t("dashboard.greetingNoName");
  const formattedDate = formatDashboardDate(now, locale, timeZone);
  const recentState = recentQuery.isPending
    ? "loading"
    : recentQuery.isError
      ? "error"
      : recentItems.length === 0
        ? "empty"
        : "ready";

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-border pb-6">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          {t("dashboard.eyebrow")}
        </p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <h1 className="font-serif text-5xl leading-tight tracking-tight sm:text-6xl">
              {greeting}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">{formattedDate}</p>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-muted-foreground">
              {t("dashboard.subtitle")}
            </p>
          </div>
          <p className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
            {t("dashboard.period.current", { days: period })}
          </p>
        </div>
      </header>

      {firstLoad ? (
        <DashboardPageSkeleton />
      ) : isNewAccount ? (
        <div className="mt-8 rounded-[6px] border border-border bg-surface p-6 sm:p-10">
          <EmptyState
            className="border-t-0 pt-0"
            title={t("dashboard.newAccount.title")}
            description={t("dashboard.newAccount.description")}
            action={{ label: t("dashboard.newAccount.action"), href: "/verificacao" }}
          />
        </div>
      ) : (
        <div className="mt-8 space-y-10">
          <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">
            {t("dashboard.summaryNote")}
          </p>
          {truncated ? (
            <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">
              {t("dashboard.sampleNote")}
            </p>
          ) : null}

          {analysesQuery.isPending ? (
            <RiskSummarySkeleton />
          ) : analysesQuery.isError ? (
            <SectionError onRetry={() => void analysesQuery.refetch()} />
          ) : summary ? (
            <RiskSummary summary={summary} period={period} />
          ) : (
            <RiskSummarySkeleton />
          )}

          <SecondaryMetrics
            summary={summary}
            period={period}
            analysesLoading={analysesQuery.isPending}
            analysesError={analysesQuery.isError}
            onRetryAnalyses={() => void analysesQuery.refetch()}
            payables={payablesQuery.data ? payablesQuery.data.items : null}
            payablesTruncated={payablesTruncated}
            payablesLoading={payablesQuery.isPending}
            payablesError={payablesQuery.isError}
            onRetryPayables={() => void payablesQuery.refetch()}
            timeZone={timeZone}
            now={now}
            truncated={truncated}
          />

          <RecentAnalyses
            items={recentItems}
            state={recentState}
            onRetry={() => void recentQuery.refetch()}
          />

          <div className="grid gap-10 lg:grid-cols-[1.35fr_1fr]">
            <RiskDistribution
              summary={summary}
              period={period}
              onPeriodChange={setPeriod}
              loading={analysesQuery.isPending}
              error={analysesQuery.isError}
              onRetry={() => void analysesQuery.refetch()}
              truncated={truncated}
            />
            <UpcomingPayables
              payables={payables}
              loading={payablesQuery.isPending}
              error={payablesQuery.isError}
              onRetry={() => void payablesQuery.refetch()}
              truncated={payablesTruncated}
              timeZone={timeZone}
              now={now}
            />
          </div>
        </div>
      )}
    </div>
  );
}
