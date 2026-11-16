"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown, RefreshCw } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/lib/i18n/provider";
import { sortRows, type SortState } from "@/lib/table/sort";
import { cn } from "@/lib/utils";

export type DataTableColumn<T> = {
  id: string;
  header: string;
  cell: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
  mono?: boolean;
  align?: "left" | "right";
  className?: string;
};

export type DataTableState = "ready" | "loading" | "empty" | "error";

export type DataTableProps<T> = {
  columns: readonly DataTableColumn<T>[];
  rows: readonly T[];
  getRowId: (row: T) => string;
  ariaLabel: string;
  state?: DataTableState;
  initialSort?: SortState;
  emptyState?: ReactNode;
  errorMessage?: string;
  onRetry?: () => void;
  loadingRows?: number;
  className?: string;
};

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  ariaLabel,
  state = "ready",
  initialSort = null,
  emptyState,
  errorMessage,
  onRetry,
  loadingRows = 4,
  className,
}: DataTableProps<T>) {
  const { t } = useI18n();
  const [sort, setSort] = useState<SortState>(initialSort);
  const sortedRows = useMemo(() => sortRows(rows, columns, sort), [rows, columns, sort]);
  const sortableColumns = columns.filter((column) => column.sortValue);
  const sortKey = sort ? `${sort.columnId}:${sort.direction}` : "";
  const activeSortColumn = sort ? columns.find((column) => column.id === sort.columnId) : undefined;
  const selectedSortLabel =
    activeSortColumn && sort
      ? `${activeSortColumn.header} ${sort.direction === "asc" ? "↑" : "↓"}`
      : "";
  const sortSelectLabel = `${t("design.dataTable.sortBy")}${
    selectedSortLabel ? `: ${selectedSortLabel}` : ""
  }`;
  const hasRows = sortedRows.length > 0;
  const showTable = state === "ready" || state === "loading";

  function toggleSort(columnId: string) {
    setSort((current) => {
      if (current?.columnId === columnId) {
        return {
          columnId,
          direction: current.direction === "asc" ? "desc" : "asc",
        };
      }

      return { columnId, direction: "asc" };
    });
  }

  function handleSortSelect(value: string) {
    const [columnId, direction] = value.split(":");

    if (columnId && (direction === "asc" || direction === "desc")) {
      setSort({ columnId, direction });
    }
  }

  const defaultEmpty = (
    <EmptyState
      title={t("design.dataTable.emptyTitle")}
      description={t("design.dataTable.emptyDescription")}
    />
  );

  if (state === "empty" || (showTable && !hasRows && state === "ready")) {
    return (
      <div className={cn("w-full min-w-0", className)}>
        <div className="rounded-[6px] border border-border bg-card p-6">
          {emptyState ?? defaultEmpty}
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div
        className={cn(
          "flex flex-col items-start gap-3 rounded-[6px] border border-border bg-card p-6",
          className,
        )}
        role="alert"
      >
        <span className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          {t("design.dataTable.stateError")}
        </span>
        <h2 className="font-serif text-2xl tracking-tight">{t("design.dataTable.errorTitle")}</h2>
        <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
          {errorMessage ?? t("design.dataTable.errorDescription")}
        </p>
        {onRetry ? (
          <Button type="button" variant="outline" onClick={onRetry}>
            <RefreshCw aria-hidden="true" />
            {t("design.dataTable.retry")}
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className={cn("w-full min-w-0", className)}>
      {sortableColumns.length > 0 ? (
        <div className="mb-2 md:hidden">
          <Select value={sortKey} onValueChange={handleSortSelect} disabled={state === "loading"}>
            <SelectTrigger aria-label={sortSelectLabel}>
              <SelectValue placeholder={t("design.dataTable.sortBy")} />
            </SelectTrigger>
            <SelectContent>
              {sortableColumns.flatMap((column) => [
                <SelectItem key={`${column.id}:asc`} value={`${column.id}:asc`}>
                  {column.header} ↑
                </SelectItem>,
                <SelectItem key={`${column.id}:desc`} value={`${column.id}:desc`}>
                  {column.header} ↓
                </SelectItem>,
              ])}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      <div className="hidden overflow-hidden rounded-[6px] border border-border md:block">
        <table
          className="w-full table-fixed text-sm"
          aria-label={ariaLabel}
          aria-busy={state === "loading"}
        >
          <colgroup>
            {columns.map((column) => (
              <col key={column.id} />
            ))}
          </colgroup>
          <thead className="bg-surface-elevated">
            <tr>
              {columns.map((column) => {
                const activeSort = sort?.columnId === column.id ? sort.direction : null;
                const ariaSort: "ascending" | "descending" | "none" =
                  activeSort === "asc"
                    ? "ascending"
                    : activeSort === "desc"
                      ? "descending"
                      : "none";

                return (
                  <th
                    key={column.id}
                    scope="col"
                    aria-sort={ariaSort}
                    className={cn(
                      "px-3 py-2 text-left font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground",
                      column.align === "right" && "text-right",
                      column.className,
                    )}
                  >
                    {column.sortValue ? (
                      <button
                        type="button"
                        disabled={state === "loading"}
                        onClick={() => toggleSort(column.id)}
                        aria-label={`${column.header}: ${t("design.dataTable.sort")}`}
                        className={cn(
                          "inline-flex w-full items-center gap-1 text-inherit",
                          column.align === "right" && "justify-end",
                        )}
                      >
                        <span className="truncate">{column.header}</span>
                        {activeSort === "asc" ? (
                          <ArrowUp className="size-3 shrink-0" aria-hidden="true" />
                        ) : activeSort === "desc" ? (
                          <ArrowDown className="size-3 shrink-0" aria-hidden="true" />
                        ) : (
                          <ChevronsUpDown className="size-3 shrink-0" aria-hidden="true" />
                        )}
                      </button>
                    ) : (
                      <span className="block truncate">{column.header}</span>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {state === "loading"
              ? Array.from({ length: Math.max(1, loadingRows) }).map((_, rowIndex) => (
                  <tr key={`loading-${rowIndex}`}>
                    {columns.map((column) => (
                      <td key={column.id} className="px-3 py-2">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    ))}
                  </tr>
                ))
              : sortedRows.map((row) => (
                  <tr key={getRowId(row)} className="align-top hover:bg-surface-elevated/60">
                    {columns.map((column) => (
                      <td
                        key={column.id}
                        className={cn(
                          "break-words px-3 py-2",
                          column.align === "right" && "text-right",
                          column.mono && "break-all font-mono tabular-nums",
                          column.className,
                        )}
                      >
                        {column.cell(row)}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      <div className="md:hidden">
        {state === "loading" ? (
          <ul
            aria-label={ariaLabel}
            className="divide-y divide-border rounded-[6px] border border-border"
          >
            {Array.from({ length: Math.max(1, loadingRows) }).map((_, index) => (
              <li key={`loading-mobile-${index}`} className="space-y-2 p-4">
                <Skeleton className="h-3 w-1/3" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
              </li>
            ))}
          </ul>
        ) : (
          <ul
            aria-label={ariaLabel}
            className="divide-y divide-border rounded-[6px] border border-border"
          >
            {sortedRows.map((row) => (
              <li key={getRowId(row)} className="p-4">
                <dl className="space-y-2">
                  {columns.map((column) => (
                    <div key={column.id} className="flex items-start justify-between gap-3">
                      <dt className="shrink-0 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground">
                        {column.header}
                      </dt>
                      <dd
                        className={cn(
                          "min-w-0 break-words text-right text-sm",
                          column.align === "right" && "text-right",
                          column.mono && "break-all font-mono tabular-nums",
                          column.className,
                        )}
                      >
                        {column.cell(row)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
