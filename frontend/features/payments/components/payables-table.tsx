"use client";

import {
  AlertCircle,
  CalendarClock,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  MoreHorizontal,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useId, useMemo, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn, type DataTableState } from "@/components/ui/data-table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import type { Payable } from "@/lib/api/schemas";
import { getDueDateRelation } from "@/lib/dashboard/date";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import {
  PAYMENTS_FILTERS,
  payableSituation,
  type PaymentSituation,
  type PaymentsFilter,
} from "@/lib/payables/library";
import { cn } from "@/lib/utils";

const SITUATION_KEYS: Record<PaymentSituation, TranslationKey> = {
  upcoming: "payments.status.upcoming",
  today: "payments.status.today",
  overdue: "payments.status.overdue",
  paid: "payments.status.paid",
  dismissed: "payments.status.dismissed",
};

const FILTER_KEYS: Record<PaymentsFilter, TranslationKey> = {
  open: "payments.list.filterOpen",
  all: "payments.list.filterAll",
  paid: "payments.list.filterPaid",
  overdue: "payments.list.filterOverdue",
};

function dueSummary(
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

function SituationBadge({
  payable,
  timeZone,
  now,
}: Readonly<{
  payable: Payable;
  timeZone: string;
  now: Date;
}>) {
  const { t } = useI18n();
  const situation = payableSituation(payable, timeZone, now);
  const label = t(SITUATION_KEYS[situation]);

  return (
    <div className="flex flex-col items-start gap-1">
      <Badge
        variant={situation === "paid" ? "petrol" : "outline"}
        className={cn(
          situation === "overdue" && "border-risk-high/40",
          situation === "today" && "border-risk-medium/50",
          situation === "dismissed" && "text-muted-foreground",
        )}
      >
        {situation === "overdue" ? (
          <AlertCircle className="size-3 text-risk-high" aria-hidden="true" />
        ) : situation === "today" ? (
          <Clock className="size-3 text-risk-medium" aria-hidden="true" />
        ) : situation === "paid" ? (
          <Check className="size-3" aria-hidden="true" />
        ) : null}
        {label}
      </Badge>
      {payable.status === "pending_confirmation" ? (
        <span className="text-[0.6rem] leading-snug text-muted-foreground">
          {t("payments.status.pendingConfirmation")}
        </span>
      ) : null}
    </div>
  );
}

function PayableActions({
  payable,
  onConfirm,
  onPay,
  onReschedule,
}: Readonly<{
  payable: Payable;
  onConfirm: (payable: Payable) => void;
  onPay: (payable: Payable) => void;
  onReschedule: (payable: Payable) => void;
}>) {
  const { t } = useI18n();
  const active =
    payable.status === "pending" ||
    payable.status === "pending_confirmation" ||
    payable.status === "overdue";

  if (!active) {
    return <span className="text-xs text-muted-foreground">{t("payments.actions.none")}</span>;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8"
          aria-label={`${t("payments.actions.menu")}: ${payable.description}`}
        >
          <MoreHorizontal aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {payable.status === "pending_confirmation" ? (
          <DropdownMenuItem onSelect={() => onConfirm(payable)}>
            <Check aria-hidden="true" />
            {t("payments.actions.confirm")}
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem onSelect={() => onPay(payable)}>
          <Check aria-hidden="true" />
          {t("payments.actions.pay")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => onReschedule(payable)}>
          <CalendarClock aria-hidden="true" />
          {t("payments.actions.reschedule")}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled title={t("payments.actions.deleteUnavailable")}>
          <Trash2 aria-hidden="true" />
          {t("payments.actions.delete")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

type PayablesMobileListProps = {
  payables: readonly Payable[];
  focusPayableId: string | null;
  state: DataTableState;
  timeZone: string;
  now: Date;
  emptyState: ReactNode;
  onRetry: () => void;
  onConfirm: (payable: Payable) => void;
  onPay: (payable: Payable) => void;
  onReschedule: (payable: Payable) => void;
};

function PayablesMobileList({
  payables,
  focusPayableId,
  state,
  timeZone,
  now,
  emptyState,
  onRetry,
  onConfirm,
  onPay,
  onReschedule,
}: PayablesMobileListProps) {
  const { t, formatCurrency, formatDate } = useI18n();

  if (state === "loading") {
    return (
      <ul aria-label={t("payments.list.aria")} aria-busy="true" className="space-y-2">
        {[0, 1, 2, 3].map((index) => (
          <li key={index} className="space-y-2 rounded-[6px] border border-border bg-card p-4">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </li>
        ))}
      </ul>
    );
  }

  if (state === "error") {
    return (
      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-[6px] border border-border bg-card p-5"
      >
        <p className="font-serif text-xl leading-tight tracking-tight">
          {t("payments.error.title")}
        </p>
        <p className="text-sm text-muted-foreground">{t("payments.error.description")}</p>
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw aria-hidden="true" />
          {t("dashboard.error.retry")}
        </Button>
      </div>
    );
  }

  if (state === "empty" || payables.length === 0) {
    return <div className="rounded-[6px] border border-border bg-card p-5">{emptyState}</div>;
  }

  return (
    <ul aria-label={t("payments.list.aria")} className="space-y-2">
      {payables.map((payable) => {
        const focused = payable.id === focusPayableId;

        return (
          <li
            key={payable.id}
            id={`payable-mobile-${payable.id}`}
            className={cn(
              "space-y-3 rounded-[6px] border border-border bg-card p-4",
              focused && "ring-1 ring-ring",
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium">{payable.description}</p>
                {focused ? (
                  <p className="mt-1 font-mono text-[0.6rem] uppercase tracking-[0.14em] text-muted-foreground">
                    {t("payments.list.focusBadge")}
                  </p>
                ) : null}
              </div>
              <SituationBadge payable={payable} timeZone={timeZone} now={now} />
            </div>

            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-border pt-3">
              <div>
                <dt className="font-mono text-[0.6rem] uppercase tracking-[0.14em] text-muted-foreground">
                  {t("payments.columns.amount")}
                </dt>
                <dd className="mt-0.5 font-mono text-xs tabular-nums">
                  {formatCurrency(Number(payable.amount), "BRL")}
                </dd>
              </div>
              <div>
                <dt className="font-mono text-[0.6rem] uppercase tracking-[0.14em] text-muted-foreground">
                  {t("payments.columns.dueDate")}
                </dt>
                <dd className="mt-0.5 text-xs">
                  <time dateTime={payable.due_date} className="block tabular-nums">
                    {formatDate(`${payable.due_date}T12:00:00Z`, {
                      dateStyle: "short",
                      timeZone,
                    })}
                  </time>
                  <span className="mt-0.5 block text-[0.65rem] text-muted-foreground">
                    {dueSummary(payable.due_date, timeZone, now, t)}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="flex justify-end border-t border-border pt-3">
              <PayableActions
                payable={payable}
                onConfirm={onConfirm}
                onPay={onPay}
                onReschedule={onReschedule}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export type PayablesTableProps = {
  payables: readonly Payable[];
  total: number;
  page: number;
  totalPages: number;
  filter: PaymentsFilter;
  focusPayableId: string | null;
  state: DataTableState;
  truncated: boolean;
  timeZone: string;
  now: Date;
  emptyState: ReactNode;
  onFilterChange: (filter: PaymentsFilter) => void;
  onPageChange: (page: number) => void;
  onRetry: () => void;
  onConfirm: (payable: Payable) => void;
  onPay: (payable: Payable) => void;
  onReschedule: (payable: Payable) => void;
};

export function PayablesTable({
  payables,
  total,
  page,
  totalPages,
  filter,
  focusPayableId,
  state,
  truncated,
  timeZone,
  now,
  emptyState,
  onFilterChange,
  onPageChange,
  onRetry,
  onConfirm,
  onPay,
  onReschedule,
}: PayablesTableProps) {
  const { t, formatCurrency, formatDate } = useI18n();
  const filterLabelId = useId();

  const columns = useMemo<readonly DataTableColumn<Payable>[]>(
    () => [
      {
        id: "description",
        header: t("payments.columns.description"),
        className: "w-[34%]",
        cell: (payable) => {
          const focused = payable.id === focusPayableId;

          return (
            <div
              id={`payable-${payable.id}`}
              className={cn(
                "min-w-0 scroll-mt-24 text-left",
                focused && "rounded-[6px] bg-surface-elevated p-2 ring-1 ring-ring",
              )}
            >
              <span className="line-clamp-2 block text-sm font-medium">{payable.description}</span>
              {focused ? (
                <span className="mt-1 block font-mono text-[0.6rem] uppercase tracking-[0.14em] text-muted-foreground">
                  {t("payments.list.focusBadge")}
                </span>
              ) : null}
            </div>
          );
        },
      },
      {
        id: "amount",
        header: t("payments.columns.amount"),
        align: "right",
        className: "w-[14%]",
        cell: (payable) => (
          <span className="font-mono text-xs tabular-nums">
            {formatCurrency(Number(payable.amount), "BRL")}
          </span>
        ),
      },
      {
        id: "dueDate",
        header: t("payments.columns.dueDate"),
        className: "w-[19%]",
        cell: (payable) => (
          <span className="block text-xs">
            <time dateTime={payable.due_date} className="block tabular-nums">
              {formatDate(`${payable.due_date}T12:00:00Z`, {
                dateStyle: "medium",
                timeZone,
              })}
            </time>
            <span className="mt-0.5 block text-[0.65rem] text-muted-foreground">
              {dueSummary(payable.due_date, timeZone, now, t)}
            </span>
          </span>
        ),
      },
      {
        id: "situation",
        header: t("payments.columns.situation"),
        className: "w-[18%]",
        cell: (payable) => <SituationBadge payable={payable} timeZone={timeZone} now={now} />,
      },
      {
        id: "actions",
        header: t("payments.columns.actions"),
        align: "right",
        className: "w-[15%]",
        cell: (payable) => (
          <PayableActions
            payable={payable}
            onConfirm={onConfirm}
            onPay={onPay}
            onReschedule={onReschedule}
          />
        ),
      },
    ],
    [focusPayableId, formatCurrency, formatDate, now, onConfirm, onPay, onReschedule, t, timeZone],
  );

  return (
    <section aria-labelledby="payments-list-title" className="min-w-0">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2
            id="payments-list-title"
            className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
          >
            {t("payments.list.title")}
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            {t("payments.list.description")}
          </p>
        </div>
        <div className="flex items-end gap-2">
          <span
            id={filterLabelId}
            className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
          >
            {t("payments.list.filter")}
          </span>
          <Select value={filter} onValueChange={(value) => onFilterChange(value as PaymentsFilter)}>
            <SelectTrigger aria-labelledby={filterLabelId} className="min-w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAYMENTS_FILTERS.map((option) => (
                <SelectItem key={option} value={option}>
                  {t(FILTER_KEYS[option])}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="mt-4">
        <div className="hidden md:block">
          <DataTable
            ariaLabel={t("payments.list.aria")}
            columns={columns}
            rows={payables}
            getRowId={(payable) => payable.id}
            state={state}
            loadingRows={6}
            errorMessage={t("payments.error.description")}
            onRetry={onRetry}
            emptyState={emptyState}
          />
        </div>
        <div className="md:hidden">
          <PayablesMobileList
            payables={payables}
            focusPayableId={focusPayableId}
            state={state}
            timeZone={timeZone}
            now={now}
            emptyState={emptyState}
            onRetry={onRetry}
            onConfirm={onConfirm}
            onPay={onPay}
            onReschedule={onReschedule}
          />
        </div>
      </div>

      {state === "ready" ? (
        <nav
          aria-label={t("payments.pagination.aria")}
          className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"
        >
          <p className="text-xs text-muted-foreground">
            {t("payments.list.count", { count: total })}
          </p>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label={t("payments.pagination.previous")}
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              <ChevronLeft aria-hidden="true" />
            </Button>
            <p className="font-mono text-xs tabular-nums text-muted-foreground">
              {t("payments.pagination.page", { page, totalPages })}
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label={t("payments.pagination.next")}
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </nav>
      ) : null}

      <div className="mt-3 space-y-1 text-[0.65rem] leading-relaxed text-muted-foreground">
        <p>{t("payments.list.issuerNote")}</p>
        <p>{t("payments.actions.deleteUnavailable")}</p>
        {truncated ? <p>{t("payments.list.sample")}</p> : null}
      </div>
    </section>
  );
}
