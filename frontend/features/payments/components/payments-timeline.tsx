"use client";

import { CalendarClock } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { getDueDateRelation } from "@/lib/dashboard/date";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import type { PayableTimelineGroup } from "@/lib/payables/library";
import { cn } from "@/lib/utils";

import { SectionError } from "@/features/dashboard/components/section-error";

const MAX_MARKERS = 6;

function relativeLabel(
  group: PayableTimelineGroup,
  timeZone: string,
  now: Date,
  t: (key: TranslationKey, params?: Record<string, string | number>) => string,
): string {
  const relation = getDueDateRelation(group.date, timeZone, now);

  if (relation === null) {
    return t("dashboard.due.unknown");
  }

  if (relation.kind === "today") {
    return t("payments.timeline.today");
  }

  if (relation.kind === "tomorrow") {
    return t("payments.timeline.tomorrow");
  }

  if (relation.kind === "inDays") {
    return t("payments.timeline.inDays", { days: relation.days });
  }

  return t("dashboard.due.unknown");
}

export type PaymentsTimelineProps = {
  groups: readonly PayableTimelineGroup[];
  loading: boolean;
  error: boolean;
  truncated: boolean;
  timeZone: string;
  now: Date;
  onRetry: () => void;
  onSelect: (payableId: string) => void;
};

export function PaymentsTimeline({
  groups,
  loading,
  error,
  truncated,
  timeZone,
  now,
  onRetry,
  onSelect,
}: PaymentsTimelineProps) {
  const { t, formatCurrency, formatDate } = useI18n();

  return (
    <section aria-labelledby="payments-timeline-title" className="min-w-0">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2
            id="payments-timeline-title"
            className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
          >
            {t("payments.timeline.title")}
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            {t("payments.timeline.description")}
          </p>
        </div>
        <span className="flex items-center gap-2 font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
          <CalendarClock className="size-3.5" aria-hidden="true" />
          {t("payments.timeline.windowEnd")}
        </span>
      </div>

      {loading ? (
        <div
          className="mt-4 rounded-[6px] border border-border bg-card p-5"
          role="status"
          aria-live="polite"
        >
          <span className="sr-only">{t("payments.loading")}</span>
          <Skeleton className="h-24 w-full" />
        </div>
      ) : error ? (
        <div className="mt-4">
          <SectionError onRetry={onRetry} message={t("payments.error.description")} />
        </div>
      ) : groups.length === 0 ? (
        <div className="mt-4 rounded-[6px] border border-border bg-card p-6">
          <EmptyState
            className="border-t-0 pt-0"
            title={t("payments.timeline.emptyTitle")}
            description={t("payments.timeline.emptyDescription")}
          />
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-[6px] border border-border bg-card">
          <div className="min-w-[44rem] px-24 py-5">
            <div className="flex items-center justify-between font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
              <span>{t("payments.timeline.windowStart")}</span>
              <span>{t("payments.timeline.windowEnd")}</span>
            </div>

            <ol aria-label={t("payments.timeline.aria")} className="relative mt-4 h-56">
              <li aria-hidden="true" className="absolute inset-x-0 top-1/2 h-px bg-border" />
              {[0, 7, 15, 22, 30].map((day) => (
                <li
                  key={day}
                  aria-hidden="true"
                  className="absolute top-1/2 h-2 w-px -translate-y-1/2 bg-border"
                  style={{ left: `${(day / 30) * 100}%` }}
                />
              ))}

              {groups.slice(0, MAX_MARKERS).map((group, index) => {
                const percent = Math.min(100, Math.max(0, (group.dayOffset / 30) * 100));
                const lane = index % 2 === 0 ? "above" : "below";
                const dateLabel = formatDate(`${group.date}T12:00:00Z`, {
                  day: "2-digit",
                  month: "short",
                  timeZone,
                });
                const relative = relativeLabel(group, timeZone, now, t);
                const amount = formatCurrency(group.totalCents / 100, "BRL");

                return (
                  <li
                    key={group.date}
                    className="absolute top-1/2 z-10"
                    style={{ left: `${percent}%` }}
                  >
                    <span
                      aria-hidden="true"
                      className="absolute left-0 top-0 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card bg-primary"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const firstId = group.payableIds[0];

                        if (firstId) {
                          onSelect(firstId);
                        }
                      }}
                      className={cn(
                        "absolute w-36 -translate-x-1/2 rounded-[6px] border border-border bg-surface p-2 text-left transition-colors hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                        lane === "above" ? "bottom-3" : "top-3",
                      )}
                    >
                      <span className="block text-[0.65rem] font-medium leading-snug">
                        {relative}
                      </span>
                      <span className="mt-0.5 block font-mono text-[0.6rem] text-muted-foreground">
                        {dateLabel}
                      </span>
                      <span className="mt-1 block font-mono text-xs tabular-nums">{amount}</span>
                      <span className="mt-0.5 block text-[0.6rem] leading-snug text-muted-foreground">
                        {t("payments.timeline.marker", { count: group.count })}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>

            <div className="flex flex-wrap items-center justify-between gap-2 text-[0.65rem] text-muted-foreground">
              <span>
                {groups.length > MAX_MARKERS
                  ? t("payments.timeline.more", {
                      count: groups.length - MAX_MARKERS,
                    })
                  : ""}
              </span>
              {truncated ? <span>{t("payments.summary.truncated")}</span> : null}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
