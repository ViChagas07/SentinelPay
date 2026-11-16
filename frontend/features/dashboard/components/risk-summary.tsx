"use client";

import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { RiskRuler } from "@/components/ui/risk-ruler";
import { formatSignedPoints } from "@/lib/dashboard/date";
import type { DashboardSummary } from "@/lib/dashboard/metrics";
import { useI18n } from "@/lib/i18n/provider";
import { bandForScore } from "@/lib/risk/ruler";

function ConformityBlock({ summary }: Readonly<{ summary: DashboardSummary }>) {
  const { t, formatNumber } = useI18n();
  const total = summary.analyzedCount;
  const low = summary.bands.low;
  const percent = summary.conformity === null ? null : Math.round(summary.conformity);

  return (
    <div className="min-w-0">
      <h3 className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
        {t("dashboard.conformity.label")}
      </h3>

      {percent === null ? (
        <p className="mt-3 font-serif text-2xl leading-tight tracking-tight">
          {t("dashboard.conformity.empty")}
        </p>
      ) : (
        <>
          <p className="mt-3 font-serif text-4xl leading-none tracking-tight">
            {t("dashboard.conformity.value", {
              percent: formatNumber(percent, { maximumFractionDigits: 0 }),
            })}
          </p>
          <div
            role="progressbar"
            aria-label={t("dashboard.conformity.label")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            aria-valuetext={t("dashboard.conformity.aria", { percent })}
            className="mt-3 h-2 w-full overflow-hidden rounded-[2px] border border-border bg-surface-elevated"
          >
            <div
              className="h-full bg-risk-low"
              style={{ width: `${percent}%` }}
              aria-hidden="true"
            />
          </div>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            {t("dashboard.conformity.description", { low, total })}
          </p>
        </>
      )}
    </div>
  );
}
function Variation({ summary, period }: Readonly<{ summary: DashboardSummary; period: number }>) {
  const { t, locale } = useI18n();
  const current = summary.currentAverage === null ? null : Math.round(summary.currentAverage);
  const previous = summary.previousAverage === null ? null : Math.round(summary.previousAverage);
  const delta = current !== null && previous !== null ? current - previous : null;

  if (delta === null) {
    return (
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        {t("dashboard.risk.variationNoBase")}
      </p>
    );
  }

  const Icon = delta > 0 ? ArrowUpRight : delta < 0 ? ArrowDownRight : Minus;

  return (
    <p className="mt-3 inline-flex items-center gap-1.5 text-sm text-muted-foreground">
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      <span className="tabular-nums text-foreground">
        {t("dashboard.risk.variation", {
          value: formatSignedPoints(delta, locale),
          days: period,
        })}
      </span>
    </p>
  );
}

export function RiskSummary({
  summary,
  period,
}: Readonly<{ summary: DashboardSummary; period: number }>) {
  const { t } = useI18n();
  const displayAverage =
    summary.currentAverage === null ? null : Math.round(summary.currentAverage);

  if (displayAverage === null) {
    return (
      <section
        aria-labelledby="dashboard-risk-title"
        className="rounded-[6px] border border-border bg-surface p-5 sm:p-6"
      >
        <h2
          id="dashboard-risk-title"
          className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground"
        >
          {t("dashboard.risk.label")}
        </h2>
        <div className="mt-4 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <div className="min-w-0">
            <p className="font-serif text-3xl leading-tight tracking-tight">
              {t("dashboard.risk.emptyTitle")}
            </p>
            <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">
              {t("dashboard.risk.emptyDescription")}
            </p>
            <Button asChild variant="outline" size="sm" className="mt-4">
              <Link href="/verificacao">{t("dashboard.actions.openVerification")}</Link>
            </Button>
          </div>
          <div className="border-t border-border pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
            <ConformityBlock summary={summary} />
          </div>
        </div>
      </section>
    );
  }

  const band = bandForScore(displayAverage);

  return (
    <section
      aria-labelledby="dashboard-risk-title"
      className="grid gap-0 rounded-[6px] border border-border bg-surface lg:grid-cols-[1fr_1.1fr_0.9fr]"
    >
      <div className="min-w-0 p-5 sm:p-6">
        <h2
          id="dashboard-risk-title"
          className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground"
        >
          {t("dashboard.risk.label")}
        </h2>
        <p className="mt-1 font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
          {t("dashboard.period.current", { days: period })}
        </p>

        <div className="mt-4 flex items-end gap-2">
          <p className="font-serif text-7xl leading-none tracking-tight tabular-nums">
            {displayAverage}
          </p>
          <span className="pb-1 font-mono text-xs text-muted-foreground">
            {t("dashboard.risk.outOf")}
          </span>
        </div>

        <Variation summary={summary} period={period} />

        <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
          {summary.flaggedCount === 0
            ? t("dashboard.risk.contextLow", { total: summary.analyzedCount })
            : t("dashboard.risk.context", {
                flagged: summary.flaggedCount,
                total: summary.analyzedCount,
              })}
        </p>

        <p className="mt-3 max-w-md text-xs leading-relaxed text-muted-foreground">
          {t("dashboard.risk.bandNote")}
        </p>
      </div>

      <div className="flex min-w-0 flex-col justify-center border-t border-border p-5 sm:p-6 lg:border-l lg:border-t-0">
        <RiskRuler score={displayAverage} band={band} variant="large" />
      </div>

      <div className="min-w-0 border-t border-border p-5 sm:p-6 lg:border-l lg:border-t-0">
        <ConformityBlock summary={summary} />
      </div>
    </section>
  );
}
