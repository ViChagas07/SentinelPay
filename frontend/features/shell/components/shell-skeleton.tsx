"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/lib/i18n/provider";

export function ShellSkeleton() {
  const { t } = useI18n();

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={t("shell.session.loading")}
      className="flex min-h-dvh w-full min-w-0 bg-background"
    >
      <div className="hidden w-64 shrink-0 border-r border-border bg-surface p-4 lg:block">
        <Skeleton className="h-8 w-40" />
        <div className="mt-8 space-y-2">
          {Array.from({ length: 7 }).map((_, index) => (
            <Skeleton key={index} className="h-9 w-full" />
          ))}
        </div>
        <div className="mt-8 space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-16 items-center gap-3 border-b border-border px-4">
          <Skeleton className="size-9 lg:hidden" />
          <Skeleton className="h-5 w-40" />
          <div className="ml-auto flex gap-2">
            <Skeleton className="h-9 w-24" />
            <Skeleton className="size-9" />
            <Skeleton className="size-9" />
          </div>
        </div>
        <div className="space-y-4 p-6">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-12 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
          <div className="grid gap-4 pt-6 md:grid-cols-3">
            <Skeleton className="h-36 w-full" />
            <Skeleton className="h-36 w-full" />
            <Skeleton className="h-36 w-full" />
          </div>
        </div>
      </div>
      <span className="sr-only">{t("shell.session.loading")}</span>
    </div>
  );
}
