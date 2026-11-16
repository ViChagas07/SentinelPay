"use client";

import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RiskRuler } from "@/components/ui/risk-ruler";
import { Skeleton } from "@/components/ui/skeleton";
import type { AnalysisKind, AnalysisStatus } from "@/lib/api/schemas";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { formatRelativeTime } from "@/lib/dashboard/date";
import { isActiveStatus } from "@/lib/verification/polling";

import { useRecentVerifications } from "../hooks/use-verification";

const STATUS_KEYS: Record<AnalysisStatus, TranslationKey> = {
  queued: "dashboard.status.queued",
  processing: "dashboard.status.processing",
  completed: "dashboard.status.completed",
  degraded: "dashboard.status.degraded",
  failed: "dashboard.status.failed",
};

const KIND_KEYS: Record<AnalysisKind, TranslationKey> = {
  boleto: "dashboard.kind.boleto",
  payslip: "dashboard.kind.payslip",
  receipt: "dashboard.kind.receipt",
};

export function RecentVerifications() {
  const { t, locale } = useI18n();
  const query = useRecentVerifications(6);
  const items = query.data?.items ?? [];

  return (
    <section aria-labelledby="verification-recent-title" className="min-w-0">
      <div>
        <h2
          id="verification-recent-title"
          className="font-serif text-2xl leading-tight tracking-tight"
        >
          {t("verification.recent.title")}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {t("verification.recent.description")}
        </p>
      </div>

      {query.isPending ? (
        <ul className="mt-4 space-y-2" aria-label={t("verification.recent.aria")}>
          {Array.from({ length: 3 }).map((_, index) => (
            <li key={index} className="space-y-2 rounded-[6px] border border-border p-3">
              <Skeleton className="h-3 w-1/3" />
              <Skeleton className="h-3 w-2/3" />
            </li>
          ))}
        </ul>
      ) : query.isError ? (
        <div role="alert" className="mt-4 rounded-[6px] border border-border bg-surface p-4">
          <p className="flex items-center gap-2 text-sm">
            <AlertCircle className="size-4" aria-hidden="true" />
            {t("verification.recent.error")}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => void query.refetch()}
          >
            <RefreshCw aria-hidden="true" />
            {t("common.retry")}
          </Button>
        </div>
      ) : items.length === 0 ? (
        <div className="mt-4 rounded-[6px] border border-border bg-surface p-4">
          <p className="text-sm font-medium">{t("verification.recent.emptyTitle")}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {t("verification.recent.emptyDescription")}
          </p>
        </div>
      ) : (
        <ul className="mt-4 space-y-2" aria-label={t("verification.recent.aria")}>
          {items.map((item) => (
            <li key={item.id}>
              <Link
                href={`/verificacao/${item.id}`}
                className="block rounded-[6px] border border-border bg-surface p-3 transition-colors hover:bg-surface-elevated focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <span className="sr-only">{t("verification.recent.open", { id: item.id })}</span>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-xs">#{item.id.slice(0, 8)}</span>
                  <Badge variant="outline">
                    {isActiveStatus(item.status) ? (
                      <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                    ) : null}
                    {t(STATUS_KEYS[item.status])}
                  </Badge>
                </div>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>{t(KIND_KEYS[item.kind])}</span>
                  <span>{formatRelativeTime(item.created_at, locale)}</span>
                </div>
                {item.score !== null && item.band !== null ? (
                  <div className="mt-2">
                    <RiskRuler score={item.score} band={item.band} variant="compact" />
                  </div>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
