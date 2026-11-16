"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/lib/i18n/provider";

export function DashboardPageSkeleton() {
  const { t } = useI18n();

  return (
    <div className="mt-8 space-y-8" role="status" aria-live="polite">
      <span className="sr-only">{t("dashboard.loading")}</span>

      <div className="grid gap-4 rounded-[6px] border border-border bg-surface p-5 lg:grid-cols-3">
        <div className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-16 w-32" />
          <Skeleton className="h-3 w-40" />
          <Skeleton className="h-3 w-36" />
        </div>
        <div className="space-y-3">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-2 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-3 w-full" />
        </div>
        <div className="space-y-3">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-10 w-20" />
          <Skeleton className="h-2 w-full" />
          <Skeleton className="h-3 w-full" />
        </div>
      </div>

      <div className="space-y-3">
        <Skeleton className="h-3 w-28" />
        {[0, 1, 2].map((index) => (
          <Skeleton key={index} className="h-12 w-full" />
        ))}
      </div>

      <div className="space-y-3">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-56 w-full" />
      </div>
    </div>
  );
}

export function RiskSummarySkeleton() {
  const { t } = useI18n();

  return (
    <div
      className="grid gap-0 rounded-[6px] border border-border bg-surface lg:grid-cols-[1fr_1.1fr_0.9fr]"
      role="status"
      aria-live="polite"
    >
      <span className="sr-only">{t("dashboard.loading")}</span>
      <div className="space-y-3 p-5 sm:p-6">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-16 w-28" />
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-3 w-48" />
        <Skeleton className="h-3 w-36" />
      </div>
      <div className="space-y-3 border-t border-border p-5 sm:p-6 lg:border-l lg:border-t-0">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-2 w-full" />
        <Skeleton className="h-4 w-full" />
      </div>
      <div className="space-y-3 border-t border-border p-5 sm:p-6 lg:border-l lg:border-t-0">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-10 w-20" />
        <Skeleton className="h-2 w-full" />
        <Skeleton className="h-3 w-full" />
      </div>
    </div>
  );
}
