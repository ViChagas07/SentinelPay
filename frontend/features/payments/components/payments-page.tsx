"use client";

import { Info, Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DataTableState } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { useSession } from "@/features/auth/hooks/use-session";
import { resolveTimeZone } from "@/lib/dashboard/date";
import type { Payable } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import {
  ACTIVE_PAYABLE_STATUSES,
  buildPayableTimeline,
  filterPayables,
  paginatePayables,
  payableSituation,
  sortPayables,
  statusesForFilter,
  summarizeActivePayables,
  TIMELINE_DAYS,
  type PaymentsFilter,
} from "@/lib/payables/library";

import { usePayableSample } from "@/features/payables/hooks/use-payables-library";
import { PayableActionDialog, type PayableActionRequest } from "./payable-action-dialog";
import { PayablesTable } from "./payables-table";
import { PaymentsSummary } from "./payments-summary";
import { PaymentsTimeline } from "./payments-timeline";
import { ReceiptDialog } from "./receipt-dialog";
import { RemindersPanel } from "./reminders-panel";

const SITUATION_KEYS = {
  upcoming: "payments.status.upcoming",
  today: "payments.status.today",
  overdue: "payments.status.overdue",
  paid: "payments.status.paid",
  dismissed: "payments.status.dismissed",
} as const;

function FocusPayableCard({
  payable,
  timeZone,
  now,
}: Readonly<{ payable: Payable; timeZone: string; now: Date }>) {
  const { t, formatCurrency, formatDate } = useI18n();

  return (
    <div
      role="status"
      className="rounded-[6px] border border-border bg-surface p-4 ring-1 ring-ring"
    >
      <p className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-muted-foreground">
        {t("payments.list.focusBadge")}
      </p>
      <div className="mt-1 flex flex-wrap items-end justify-between gap-3">
        <p className="min-w-0 text-sm font-medium">{payable.description}</p>
        <Badge variant="outline">
          {t(SITUATION_KEYS[payableSituation(payable, timeZone, now)])}
        </Badge>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="font-mono tabular-nums">
          {formatCurrency(Number(payable.amount), "BRL")}
        </span>
        <span>{formatDate(`${payable.due_date}T12:00:00Z`, { dateStyle: "medium" })}</span>
      </div>
    </div>
  );
}

export function PaymentsPage({ focusPayableId }: Readonly<{ focusPayableId?: string }>) {
  const { t } = useI18n();
  const { user, status } = useSession();
  const timeZone = resolveTimeZone(user?.timezone);
  const [filter, setFilter] = useState<PaymentsFilter>(focusPayableId ? "all" : "open");
  const [page, setPage] = useState(1);
  const [selectedPayableId, setSelectedPayableId] = useState<string | null>(focusPayableId ?? null);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [actionRequest, setActionRequest] = useState<PayableActionRequest | null>(null);

  const timelineQuery = usePayableSample(ACTIVE_PAYABLE_STATUSES);
  const listStatuses = statusesForFilter(filter);
  const listQuery = usePayableSample(listStatuses);
  const now = useMemo(() => {
    const stamp = Math.max(listQuery.dataUpdatedAt, timelineQuery.dataUpdatedAt);

    return new Date(stamp);
  }, [listQuery.dataUpdatedAt, timelineQuery.dataUpdatedAt]);
  const activeItems = useMemo(() => timelineQuery.data?.items ?? [], [timelineQuery.data]);
  const summary = useMemo(
    () => summarizeActivePayables(activeItems, timeZone, now),
    [activeItems, now, timeZone],
  );
  const timelineGroups = useMemo(
    () => buildPayableTimeline(activeItems, timeZone, now, TIMELINE_DAYS),
    [activeItems, now, timeZone],
  );
  const listItems = useMemo(
    () => sortPayables(filterPayables(listQuery.data?.items ?? [], filter, timeZone, now)),
    [filter, listQuery.data, now, timeZone],
  );
  const pageData = paginatePayables(listItems, page);
  const focusedPayable = useMemo(
    () =>
      selectedPayableId
        ? (listQuery.data?.items.find((item) => item.id === selectedPayableId) ??
          timelineQuery.data?.items.find((item) => item.id === selectedPayableId) ??
          null)
        : null,
    [listQuery.data, selectedPayableId, timelineQuery.data],
  );
  const focusedMissing = Boolean(selectedPayableId) && !focusedPayable && listQuery.isSuccess;
  const timelineFirstLoad = timelineQuery.isPending && !timelineQuery.data;
  const listFirstLoad = listQuery.isPending && !listQuery.data;
  const listError = listQuery.isError && !listQuery.data;
  const listState: DataTableState = listFirstLoad
    ? "loading"
    : listError
      ? "error"
      : pageData.total > 0
        ? "ready"
        : "empty";

  if (status !== "authenticated" || !user) {
    return (
      <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8" aria-busy="true">
        <div className="h-10 w-2/3 animate-pulse rounded bg-surface-elevated motion-reduce:animate-none" />
      </div>
    );
  }

  function changeFilter(next: PaymentsFilter): void {
    setFilter(next);
    setPage(1);
  }

  function selectPayable(payableId: string): void {
    setSelectedPayableId(payableId);
    changeFilter("all");
  }

  const emptyState =
    filter === "open" || (listItems.length === 0 && filter === "all") ? (
      <EmptyState
        className="border-t-0 pt-0"
        title={t("payments.list.emptyTitle")}
        description={t("payments.list.emptyDescription")}
        action={{
          label: t("payments.newReceipt"),
          onClick: () => setReceiptOpen(true),
        }}
      />
    ) : (
      <EmptyState
        className="border-t-0 pt-0"
        title={t("payments.list.filteredEmptyTitle")}
        description={t("payments.list.filteredEmptyDescription")}
        action={{
          label: t("payments.list.filteredEmptyAction"),
          onClick: () => changeFilter("all"),
        }}
      />
    );

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-border pb-6">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          {t("payments.eyebrow")}
        </p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <h1 className="font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
              {t("payments.title")}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              {t("payments.description")}
            </p>
          </div>
          <Button type="button" onClick={() => setReceiptOpen(true)}>
            <Plus aria-hidden="true" />
            {t("payments.newReceipt")}
          </Button>
        </div>
      </header>

      <div className="mt-8 space-y-8">
        <PaymentsSummary
          summary={timelineQuery.data ? summary : null}
          truncated={Boolean(timelineQuery.data?.truncated)}
          loading={timelineFirstLoad}
        />

        <PaymentsTimeline
          groups={timelineGroups}
          loading={timelineFirstLoad}
          error={timelineQuery.isError && !timelineQuery.data}
          truncated={Boolean(timelineQuery.data?.truncated)}
          timeZone={timeZone}
          now={now}
          onRetry={() => void timelineQuery.refetch()}
          onSelect={selectPayable}
        />

        {focusedPayable ? (
          <FocusPayableCard payable={focusedPayable} timeZone={timeZone} now={now} />
        ) : focusedMissing ? (
          <div
            role="status"
            className="flex flex-wrap items-center justify-between gap-3 rounded-[6px] border border-border bg-surface p-4"
          >
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Info className="size-4 shrink-0" aria-hidden="true" />
              {t("payments.focusNotice", { id: selectedPayableId ?? "" })}
            </p>
            <Button type="button" size="sm" variant="outline" onClick={() => changeFilter("all")}>
              {t("payments.focusAction")}
            </Button>
          </div>
        ) : null}

        <PayablesTable
          payables={pageData.items}
          total={pageData.total}
          page={pageData.page}
          totalPages={pageData.totalPages}
          filter={filter}
          focusPayableId={selectedPayableId}
          state={listState}
          truncated={Boolean(listQuery.data?.truncated)}
          timeZone={timeZone}
          now={now}
          emptyState={emptyState}
          onFilterChange={changeFilter}
          onPageChange={setPage}
          onRetry={() => void listQuery.refetch()}
          onConfirm={(payable) => setActionRequest({ kind: "confirm", payable })}
          onPay={(payable) => setActionRequest({ kind: "pay", payable })}
          onReschedule={(payable) => setActionRequest({ kind: "reschedule", payable })}
        />

        <RemindersPanel />
      </div>

      {receiptOpen ? <ReceiptDialog onClose={() => setReceiptOpen(false)} /> : null}
      <PayableActionDialog request={actionRequest} onClose={() => setActionRequest(null)} />
    </div>
  );
}
