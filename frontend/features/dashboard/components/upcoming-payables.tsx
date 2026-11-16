"use client";

import { ArrowRight, ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Payable, PayableStatus } from "@/lib/api/schemas";
import { getDueDateRelation } from "@/lib/dashboard/date";
import { selectUpcomingPayables } from "@/lib/dashboard/metrics";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

import { SectionError } from "./section-error";

const UPCOMING_LIMIT = 5;

const STATUS_KEYS: Record<PayableStatus, TranslationKey> = {
  pending_confirmation: "dashboard.payable.pending_confirmation",
  pending: "dashboard.payable.pending",
  overdue: "dashboard.payable.overdue",
  paid: "dashboard.payable.paid",
  dismissed: "dashboard.payable.dismissed",
};

function dueLabel(
  dueDate: string,
  timeZone: string,
  now: Date,
  t: (key: TranslationKey, params?: Record<string, string | number>) => string,
): string {
  const relation = getDueDateRelation(dueDate, timeZone, now);

  if (relation === null) {
    return t("dashboard.due.unknown");
  }

  switch (relation.kind) {
    case "today":
      return t("dashboard.due.today");
    case "tomorrow":
      return t("dashboard.due.tomorrow");
    case "inDays":
      return t("dashboard.due.inDays", { days: relation.days });
    case "yesterday":
      return t("dashboard.due.yesterday");
    case "daysAgo":
      return t("dashboard.due.daysAgo", { days: relation.days });
  }
}

export type UpcomingPayablesProps = {
  payables: readonly Payable[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  truncated: boolean;
  timeZone: string;
  now: Date;
};

export function UpcomingPayables({
  payables,
  loading,
  error,
  onRetry,
  truncated,
  timeZone,
  now,
}: UpcomingPayablesProps) {
  const { t, formatCurrency } = useI18n();
  const upcoming = selectUpcomingPayables(payables, UPCOMING_LIMIT);

  return (
    <section aria-labelledby="dashboard-upcoming-title" className="min-w-0">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2
            id="dashboard-upcoming-title"
            className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
          >
            {t("dashboard.upcoming.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {t("dashboard.upcoming.description")}
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/pagamentos">
            {t("dashboard.upcoming.viewAll")}
            <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
      </div>

      {loading ? (
        <div
          className="mt-4 space-y-2 border-t border-border pt-2"
          role="status"
          aria-live="polite"
        >
          <span className="sr-only">{t("dashboard.loading")}</span>
          {[0, 1, 2, 3].map((index) => (
            <div key={index} className="flex items-center justify-between gap-4 py-3">
              <div className="min-w-0 flex-1 space-y-2">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-3 w-1/3" />
              </div>
              <Skeleton className="h-4 w-20 shrink-0" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="mt-4">
          <SectionError onRetry={onRetry} />
        </div>
      ) : upcoming.length === 0 ? (
        <div className="mt-4 rounded-[6px] border border-dashed border-border p-5">
          <p className="font-serif text-xl leading-tight tracking-tight">
            {t("dashboard.upcoming.emptyTitle")}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {t("dashboard.upcoming.emptyDescription")}
          </p>
        </div>
      ) : (
        <>
          <ul aria-label={t("dashboard.upcoming.title")} className="mt-4 border-t border-border">
            {upcoming.map((payable) => (
              <li key={payable.id} className="border-b border-border">
                <Link
                  href="/pagamentos"
                  className="group flex items-start justify-between gap-4 py-3 transition-colors hover:bg-surface-elevated/60"
                >
                  <span className="min-w-0">
                    <span className="line-clamp-2 block text-sm font-medium">
                      {payable.description}
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>{dueLabel(payable.due_date, timeZone, now, t)}</span>
                      <span aria-hidden="true">·</span>
                      <Badge variant="outline">{t(STATUS_KEYS[payable.status])}</Badge>
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="font-mono text-sm tabular-nums">
                      {formatCurrency(Number(payable.amount), "BRL")}
                    </span>
                    <ArrowUpRight className="size-4 text-muted-foreground" aria-hidden="true" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {truncated ? (
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              {t("dashboard.upcoming.sample")}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
