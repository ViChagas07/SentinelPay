"use client";

import { Skeleton } from "@/components/ui/skeleton";
import type { PaymentsSummary } from "@/lib/payables/library";
import { useI18n } from "@/lib/i18n/provider";

function displayCount(value: number, truncated: boolean): string {
  return value > 0 && truncated ? `${value}+` : String(value);
}

export type PaymentsSummaryProps = {
  summary: PaymentsSummary | null;
  truncated: boolean;
  loading: boolean;
};

export function PaymentsSummary({ summary, truncated, loading }: PaymentsSummaryProps) {
  const { t } = useI18n();

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-3" role="status" aria-live="polite">
        <span className="sr-only">{t("payments.loading")}</span>
        {[0, 1, 2].map((index) => (
          <div key={index} className="space-y-2 rounded-[6px] border border-border p-4">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-8 w-12" />
          </div>
        ))}
      </div>
    );
  }

  const values = [
    { key: "upcoming" as const, label: t("payments.summary.upcoming") },
    { key: "today" as const, label: t("payments.summary.today") },
    { key: "overdue" as const, label: t("payments.summary.overdue") },
  ];

  return (
    <section aria-label={t("payments.summary.note")} className="space-y-2">
      <div className="grid divide-y divide-border rounded-[6px] border border-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {values.map((item) => (
          <div key={item.key} className="p-4">
            <p className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
              {item.label}
            </p>
            <p className="mt-1 font-serif text-4xl leading-none tracking-tight tabular-nums">
              {summary ? displayCount(summary[item.key], truncated) : t("library.countPending")}
            </p>
          </div>
        ))}
      </div>
      <p className="text-[0.65rem] leading-relaxed text-muted-foreground">
        {truncated ? t("payments.summary.truncated") : t("payments.summary.note")}
      </p>
    </section>
  );
}
