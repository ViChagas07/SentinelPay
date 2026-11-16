"use client";

import { ArrowRight, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn, type DataTableState } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { RiskBadge } from "@/components/ui/risk-badge";
import { RiskRuler } from "@/components/ui/risk-ruler";
import type { AnalysisKind, AnalysisListItem, AnalysisStatus } from "@/lib/api/schemas";
import { formatRelativeTime } from "@/lib/dashboard/date";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

const KIND_KEYS: Record<AnalysisKind, TranslationKey> = {
  boleto: "dashboard.kind.boleto",
  payslip: "dashboard.kind.payslip",
  receipt: "dashboard.kind.receipt",
};

const STATUS_KEYS: Record<AnalysisStatus, TranslationKey> = {
  queued: "dashboard.status.queued",
  processing: "dashboard.status.processing",
  completed: "dashboard.status.completed",
  degraded: "dashboard.status.degraded",
  failed: "dashboard.status.failed",
};

export type RecentAnalysesProps = {
  items: readonly AnalysisListItem[];
  state: DataTableState;
  onRetry: () => void;
};

export function RecentAnalyses({ items, state, onRetry }: RecentAnalysesProps) {
  const { t, locale } = useI18n();

  const columns = useMemo<readonly DataTableColumn<AnalysisListItem>[]>(
    () => [
      {
        id: "analysis",
        header: t("dashboard.recent.columnAnalysis"),
        cell: (row) => (
          <div className="min-w-0">
            <Link
              href={`/verificacao/${row.id}`}
              aria-label={t("dashboard.recent.openAnalysis", { id: row.id })}
              className="rounded-[4px] font-mono text-xs underline-offset-4 hover:underline"
            >
              #{row.id.slice(0, 8)}
            </Link>
            <span className="mt-1 block text-xs text-muted-foreground">
              {t(KIND_KEYS[row.kind])}
            </span>
          </div>
        ),
      },
      {
        id: "issuer",
        header: t("dashboard.recent.columnIssuer"),
        cell: () => (
          <span className="text-xs text-muted-foreground">{t("dashboard.recent.unavailable")}</span>
        ),
      },
      {
        id: "taxId",
        header: t("dashboard.recent.columnTaxId"),
        cell: () => (
          <span className="text-xs text-muted-foreground">{t("dashboard.recent.unavailable")}</span>
        ),
      },
      {
        id: "amount",
        header: t("dashboard.recent.columnAmount"),
        align: "right",
        cell: () => (
          <span className="text-xs text-muted-foreground">{t("dashboard.recent.unavailable")}</span>
        ),
      },
      {
        id: "risk",
        header: t("dashboard.recent.columnRiskClass"),
        cell: (row) => (
          <div className="min-w-0 space-y-1">
            {row.score !== null && row.band !== null ? (
              <>
                <RiskRuler score={row.score} band={row.band} variant="compact" />
                <RiskBadge band={row.band} showIcon={false} />
              </>
            ) : (
              <Badge variant="outline">{t(STATUS_KEYS[row.status])}</Badge>
            )}
          </div>
        ),
      },
      {
        id: "date",
        header: t("dashboard.recent.columnDate"),
        cell: (row) => (
          <span className="text-xs text-muted-foreground">
            {formatRelativeTime(row.created_at, locale)}
          </span>
        ),
      },
      {
        id: "open",
        header: t("dashboard.recent.columnOpen"),
        align: "right",
        cell: (row) => (
          <Link
            href={`/verificacao/${row.id}`}
            aria-label={t("dashboard.recent.open")}
            className="inline-flex rounded-[4px] p-1 text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
          >
            <ArrowUpRight className="size-4" aria-hidden="true" />
          </Link>
        ),
      },
    ],
    [locale, t],
  );

  return (
    <section aria-labelledby="dashboard-recent-title" className="min-w-0">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2
            id="dashboard-recent-title"
            className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
          >
            {t("dashboard.recent.title")}
          </h2>
          <p className="mt-2 max-w-3xl text-xs leading-relaxed text-muted-foreground sm:text-sm">
            {t("dashboard.recent.missingFields")}
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/verificacao">
            {t("dashboard.recent.viewAll")}
            <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
      </div>

      <div className="mt-5">
        <DataTable
          ariaLabel={t("dashboard.recent.tableAria")}
          columns={columns}
          rows={items}
          getRowId={(row) => row.id}
          state={state}
          loadingRows={6}
          errorMessage={t("dashboard.recent.error")}
          onRetry={onRetry}
          emptyState={
            <EmptyState
              className="border-t-0 pt-0"
              title={t("dashboard.recent.emptyTitle")}
              description={t("dashboard.recent.emptyDescription")}
              action={{
                label: t("dashboard.actions.openVerification"),
                href: "/verificacao",
              }}
            />
          }
        />
      </div>
    </section>
  );
}
