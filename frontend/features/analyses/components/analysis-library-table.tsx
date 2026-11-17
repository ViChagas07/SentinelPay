"use client";

import { AlertCircle, ArrowUpRight, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useMemo,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn, type DataTableState } from "@/components/ui/data-table";
import { RiskBadge } from "@/components/ui/risk-badge";
import { RiskRuler } from "@/components/ui/risk-ruler";
import { Skeleton } from "@/components/ui/skeleton";
import type { AnalysisListItem, AnalysisStatus } from "@/lib/api/schemas";
import type { LibraryKind, LibraryView } from "@/lib/analyses/library";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { isActiveStatus } from "@/lib/verification/polling";
import { cn } from "@/lib/utils";

export const LIBRARY_STATUS_KEYS: Record<AnalysisStatus, TranslationKey> = {
  queued: "dashboard.status.queued",
  running: "dashboard.status.running",
  processing: "dashboard.status.processing",
  cancelling: "dashboard.status.cancelling",
  cancelled: "dashboard.status.cancelled",
  completed: "dashboard.status.completed",
  degraded: "dashboard.status.degraded",
  failed: "dashboard.status.failed",
};

function StatusBadge({ status }: Readonly<{ status: AnalysisStatus }>) {
  const { t } = useI18n();
  const active = isActiveStatus(status);
  const failed = status === "failed";
  const cancelled = status === "cancelled";

  return (
    <Badge
      variant="outline"
      className={cn(
        "max-w-full gap-1.5 whitespace-normal",
        (failed || cancelled) && "border-risk-high/40",
      )}
    >
      {active ? (
        <Loader2
          className="size-3 shrink-0 animate-spin motion-reduce:animate-none"
          aria-hidden="true"
        />
      ) : failed || cancelled ? (
        <AlertCircle className="size-3 shrink-0 text-risk-high" aria-hidden="true" />
      ) : null}
      {t(LIBRARY_STATUS_KEYS[status])}
    </Badge>
  );
}

function UnavailableValue({ hint }: Readonly<{ hint?: string }>) {
  const { t } = useI18n();

  return (
    <span className="block text-xs text-muted-foreground" title={t("library.unavailableHint")}>
      <span className="block">{t("library.unavailable")}</span>
      {hint ? <span className="mt-0.5 block text-[0.65rem] leading-snug">{hint}</span> : null}
    </span>
  );
}

function MobileField({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="min-w-0">
      <dt className="font-mono text-[0.6rem] uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 break-words text-xs text-foreground">{value}</dd>
    </div>
  );
}

type MobileAnalysisListProps = {
  kind: LibraryKind;
  view: LibraryView | null;
  state: DataTableState;
  emptyState: ReactNode;
  onRetry: () => void;
  onRowKeyDown: (event: ReactKeyboardEvent<HTMLAnchorElement>) => void;
};

function MobileAnalysisList({
  kind,
  view,
  state,
  emptyState,
  onRetry,
  onRowKeyDown,
}: MobileAnalysisListProps) {
  const { t, formatDate } = useI18n();
  const ariaLabel = t(kind === "payslip" ? "folha.tableAria" : "boletos.tableAria");

  if (state === "loading") {
    return (
      <ul
        aria-label={ariaLabel}
        aria-busy="true"
        className="divide-y divide-border rounded-[6px] border border-border"
      >
        {Array.from({ length: 6 }).map((_, index) => (
          <li key={`mobile-loading-${index}`} className="space-y-2 p-4">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </li>
        ))}
      </ul>
    );
  }

  if (state === "error") {
    return (
      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-[6px] border border-border bg-card p-6"
      >
        <span className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          {t("design.dataTable.stateError")}
        </span>
        <h2 className="font-serif text-2xl tracking-tight">{t("design.dataTable.errorTitle")}</h2>
        <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
          {t("library.error")}
        </p>
        <Button type="button" variant="outline" onClick={onRetry}>
          <RefreshCw aria-hidden="true" />
          {t("design.dataTable.retry")}
        </Button>
      </div>
    );
  }

  if (state === "empty" || !view || view.items.length === 0) {
    return <div className="rounded-[6px] border border-border bg-card p-6">{emptyState}</div>;
  }

  return (
    <ul
      aria-label={ariaLabel}
      className="divide-y divide-border rounded-[6px] border border-border"
    >
      {view.items.map((row) => {
        const score = row.score;
        const band = row.band;
        const hasResult = score !== null && band !== null;
        const awaiting = isActiveStatus(row.status);

        return (
          <li key={row.id} className="space-y-3 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <Link
                  href={`/verificacao/${row.id}`}
                  data-analysis-row-link="true"
                  aria-label={t("library.open", { id: row.id })}
                  aria-keyshortcuts="ArrowDown ArrowUp Enter"
                  onKeyDown={onRowKeyDown}
                  className="inline-flex max-w-full items-center gap-1 rounded-[4px] font-mono text-xs tabular-nums underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  <span className="truncate">#{row.id.slice(0, 8)}</span>
                  <ArrowUpRight className="size-3 shrink-0" aria-hidden="true" />
                </Link>
                <span className="mt-0.5 block text-[0.65rem] leading-snug text-muted-foreground">
                  {t("library.columns.analysisId")}
                </span>
              </div>
              <StatusBadge status={row.status} />
            </div>

            {hasResult ? (
              <RiskRuler score={score} band={band} variant="medium" />
            ) : (
              <p className="text-xs text-muted-foreground">
                {t(awaiting ? "library.columns.awaiting" : "library.columns.noResult")}
              </p>
            )}

            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-border pt-3">
              {kind === "payslip" ? (
                <>
                  <MobileField
                    label={t("library.mobile.employer")}
                    value={t("library.unavailable")}
                  />
                  <MobileField label={t("library.mobile.cnpj")} value={t("library.unavailable")} />
                  <MobileField
                    label={t("library.columns.competency")}
                    value={t("library.unavailable")}
                  />
                  <MobileField
                    label={t("library.columns.netAmount")}
                    value={t("library.unavailable")}
                  />
                </>
              ) : (
                <>
                  <MobileField
                    label={t("library.mobile.beneficiary")}
                    value={t("library.unavailable")}
                  />
                  <MobileField label={t("library.mobile.cnpj")} value={t("library.unavailable")} />
                  <MobileField
                    label={t("library.columns.amount")}
                    value={t("library.unavailable")}
                  />
                  <MobileField
                    label={t("library.columns.dueDate")}
                    value={t("library.unavailable")}
                  />
                </>
              )}
              <div className="col-span-2 min-w-0">
                <dt className="font-mono text-[0.6rem] uppercase tracking-[0.14em] text-muted-foreground">
                  {t("library.columns.date")}
                </dt>
                <dd className="mt-0.5 text-xs text-foreground">
                  <time dateTime={row.created_at}>
                    {formatDate(row.created_at, { dateStyle: "short", timeStyle: "short" })}
                  </time>
                </dd>
              </div>
            </dl>

            <div className="flex justify-end border-t border-border pt-3">
              <Link
                href={`/verificacao/${row.id}`}
                aria-label={t("library.open", { id: row.id })}
                className="inline-flex items-center gap-1 rounded-[4px] text-xs font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                {t("library.openDossier")}
                <ArrowUpRight className="size-3.5" aria-hidden="true" />
              </Link>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export type AnalysisLibraryTableProps = {
  kind: LibraryKind;
  view: LibraryView | null;
  state: DataTableState;
  emptyState: ReactNode;
  onRetry: () => void;
};

export function AnalysisLibraryTable({
  kind,
  view,
  state,
  emptyState,
  onRetry,
}: AnalysisLibraryTableProps) {
  const { t, formatDate } = useI18n();

  const handleRowKeyDown = useCallback((event: ReactKeyboardEvent<HTMLAnchorElement>) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
      return;
    }

    const root = event.currentTarget.closest("[data-analysis-library]");

    if (!root) {
      return;
    }

    const links = Array.from(
      root.querySelectorAll<HTMLAnchorElement>("a[data-analysis-row-link]"),
    ).filter((link) => link.getClientRects().length > 0);
    const index = links.indexOf(event.currentTarget);
    const next = links[index + (event.key === "ArrowDown" ? 1 : -1)];

    if (next) {
      event.preventDefault();
      next.focus();
    }
  }, []);

  const columns = useMemo<readonly DataTableColumn<AnalysisListItem>[]>(() => {
    const documentColumn: DataTableColumn<AnalysisListItem> = {
      id: "document",
      header: t("library.columns.document"),
      className: "w-[10%]",
      cell: (row) => (
        <div className="min-w-0">
          <Link
            href={`/verificacao/${row.id}`}
            data-analysis-row-link="true"
            aria-label={t("library.open", { id: row.id })}
            aria-keyshortcuts="ArrowDown ArrowUp Enter"
            onKeyDown={handleRowKeyDown}
            className="inline-flex max-w-full items-center gap-1 rounded-[4px] font-mono text-xs tabular-nums underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <span className="truncate">#{row.id.slice(0, 8)}</span>
            <ArrowUpRight className="size-3 shrink-0" aria-hidden="true" />
          </Link>
          <span className="mt-0.5 block text-[0.65rem] leading-snug text-muted-foreground">
            {t("library.columns.analysisId")}
          </span>
        </div>
      ),
    };

    const riskColumn: DataTableColumn<AnalysisListItem> = {
      id: "risk",
      header: t("library.columns.risk"),
      className: "w-[22%]",
      cell: (row) => {
        if (row.score !== null && row.band !== null) {
          return (
            <div className="min-w-0 space-y-1">
              <div className="hidden md:block">
                <RiskRuler score={row.score} band={row.band} variant="compact" />
              </div>
              <div className="md:hidden">
                <RiskRuler score={row.score} band={row.band} variant="medium" />
              </div>
              <RiskBadge band={row.band} showIcon={false} />
            </div>
          );
        }

        const awaiting = isActiveStatus(row.status);

        return (
          <span className="text-xs text-muted-foreground">
            {t(awaiting ? "library.columns.awaiting" : "library.columns.noResult")}
          </span>
        );
      },
    };

    const statusColumn: DataTableColumn<AnalysisListItem> = {
      id: "status",
      header: t("library.columns.status"),
      className: "w-[13%]",
      cell: (row) => <StatusBadge status={row.status} />,
    };

    const dateColumn: DataTableColumn<AnalysisListItem> = {
      id: "date",
      header: t("library.columns.date"),
      className: "w-[17%]",
      cell: (row) => (
        <time dateTime={row.created_at} className="text-xs text-muted-foreground">
          {formatDate(row.created_at, { dateStyle: "short", timeStyle: "short" })}
        </time>
      ),
    };

    if (kind === "payslip") {
      return [
        documentColumn,
        {
          id: "employer",
          header: t("library.columns.employer"),
          className: "w-[17%]",
          cell: () => <UnavailableValue hint={t("library.columns.taxIdUnavailable")} />,
        },
        {
          id: "competency",
          header: t("library.columns.competency"),
          className: "w-[11%]",
          cell: () => <UnavailableValue />,
        },
        {
          id: "net",
          header: t("library.columns.netAmount"),
          align: "right",
          className: "w-[11%]",
          cell: () => <UnavailableValue />,
        },
        riskColumn,
        statusColumn,
        dateColumn,
      ];
    }

    return [
      documentColumn,
      {
        id: "beneficiary",
        header: t("library.columns.beneficiary"),
        className: "w-[17%]",
        cell: () => <UnavailableValue hint={t("library.columns.taxIdUnavailable")} />,
      },
      {
        id: "amount",
        header: t("library.columns.amount"),
        align: "right",
        className: "w-[10%]",
        cell: () => <UnavailableValue />,
      },
      {
        id: "dueDate",
        header: t("library.columns.dueDate"),
        className: "w-[11%]",
        cell: () => <UnavailableValue />,
      },
      riskColumn,
      statusColumn,
      dateColumn,
    ];
  }, [formatDate, handleRowKeyDown, kind, t]);

  return (
    <div data-analysis-library="true">
      <div className="hidden md:block">
        <DataTable
          ariaLabel={t(kind === "payslip" ? "folha.tableAria" : "boletos.tableAria")}
          columns={columns}
          rows={view?.items ?? []}
          getRowId={(row) => row.id}
          state={state}
          loadingRows={8}
          errorMessage={t("library.error")}
          onRetry={onRetry}
          emptyState={emptyState}
        />
      </div>
      <div className="md:hidden">
        <MobileAnalysisList
          kind={kind}
          view={view}
          state={state}
          emptyState={emptyState}
          onRetry={onRetry}
          onRowKeyDown={handleRowKeyDown}
        />
      </div>
    </div>
  );
}
