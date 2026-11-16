"use client";

import { ArrowDown, ArrowUp, Info } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  hasActiveLibraryFilters,
  LIBRARY_MAX_QUERY_LENGTH,
  type LibraryParams,
  type LibraryPeriod,
  type LibrarySort,
  type LibraryStatusFilter,
} from "@/lib/analyses/library";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

const PERIOD_OPTIONS: readonly { value: LibraryPeriod; labelKey: TranslationKey }[] = [
  { value: "all", labelKey: "library.filters.periodAll" },
  { value: 7, labelKey: "library.filters.periodDays" },
  { value: 30, labelKey: "library.filters.periodDays" },
  { value: 90, labelKey: "library.filters.periodDays" },
  { value: 365, labelKey: "library.filters.periodDays" },
];

const STATUS_OPTIONS: readonly { value: LibraryStatusFilter; labelKey: TranslationKey }[] = [
  { value: "all", labelKey: "library.filters.statusAll" },
  { value: "active", labelKey: "library.filters.statusActive" },
  { value: "done", labelKey: "library.filters.statusDone" },
  { value: "failed", labelKey: "library.filters.statusFailed" },
];

const SORT_OPTIONS: readonly {
  value: string;
  labelKey: TranslationKey;
  disabled?: boolean;
}[] = [
  { value: "date", labelKey: "library.filters.sortDate" },
  { value: "value", labelKey: "library.filters.sortValue", disabled: true },
  { value: "score", labelKey: "library.filters.sortScore" },
];

type LibrarySearchProps = {
  initialQuery: string;
  onSubmit: (query: string) => void;
};

function LibrarySearch({ initialQuery, onSubmit }: LibrarySearchProps) {
  const { t } = useI18n();
  const searchId = useId();
  const searchHintId = useId();
  const [query, setQuery] = useState(initialQuery);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(query.trim().slice(0, LIBRARY_MAX_QUERY_LENGTH));
  }

  return (
    <form role="search" onSubmit={submitSearch} className="space-y-1.5">
      <label
        htmlFor={searchId}
        className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
      >
        {t("library.filters.search")}
      </label>
      <div className="flex gap-2">
        <input
          id={searchId}
          type="search"
          value={query}
          maxLength={LIBRARY_MAX_QUERY_LENGTH}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("library.filters.searchPlaceholder")}
          aria-describedby={searchHintId}
          className="h-9 min-w-0 flex-1 rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button type="submit" variant="outline" size="sm" className="h-9">
          {t("library.filters.searchSubmit")}
        </Button>
      </div>
      <p id={searchHintId} className="text-[0.65rem] leading-snug text-muted-foreground">
        {t("library.filters.searchHint")}
      </p>
    </form>
  );
}

export type LibraryFiltersProps = {
  params: LibraryParams;
  onChange: (patch: Partial<LibraryParams>) => void;
  onClear: () => void;
};

export function LibraryFilters({ params, onChange, onClear }: LibraryFiltersProps) {
  const { t } = useI18n();
  const periodLabelId = useId();
  const statusLabelId = useId();
  const sortLabelId = useId();
  const unavailableId = useId();

  function selectSort(value: string) {
    if (value === "date" || value === "score") {
      onChange({ sort: value as LibrarySort });
    }
  }

  return (
    <fieldset className="min-w-0 rounded-[6px] border border-border bg-surface p-4 sm:p-5">
      <legend className="sr-only">{t("library.filters.label")}</legend>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="space-y-1.5">
          <span
            id={periodLabelId}
            className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
          >
            {t("library.filters.period")}
          </span>
          <Select
            value={String(params.period)}
            onValueChange={(value) =>
              onChange({
                period: (value === "all" ? "all" : Number(value)) as LibraryPeriod,
              })
            }
          >
            <SelectTrigger aria-labelledby={periodLabelId}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIOD_OPTIONS.map((option) => (
                <SelectItem key={String(option.value)} value={String(option.value)}>
                  {t(option.labelKey, { days: option.value })}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <span
            id={statusLabelId}
            className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
          >
            {t("library.filters.status")}
          </span>
          <Select
            value={params.status}
            onValueChange={(value) => onChange({ status: value as LibraryStatusFilter })}
          >
            <SelectTrigger aria-labelledby={statusLabelId}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {t(option.labelKey)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <LibrarySearch
          key={params.query}
          initialQuery={params.query}
          onSubmit={(query) => onChange({ query })}
        />

        <div className="space-y-1.5">
          <span
            id={sortLabelId}
            className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
          >
            {t("library.filters.sort")}
          </span>
          <div className="flex gap-2">
            <Select value={params.sort} onValueChange={selectSort}>
              <SelectTrigger aria-labelledby={sortLabelId}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value} disabled={option.disabled}>
                    {t(option.labelKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-9 shrink-0"
              aria-label={`${t("library.filters.direction")}: ${t(
                params.direction === "asc" ? "library.filters.asc" : "library.filters.desc",
              )}`}
              onClick={() => onChange({ direction: params.direction === "asc" ? "desc" : "asc" })}
            >
              {params.direction === "asc" ? (
                <ArrowUp aria-hidden="true" />
              ) : (
                <ArrowDown aria-hidden="true" />
              )}
              <span className="hidden sm:inline">
                {t(params.direction === "asc" ? "library.filters.asc" : "library.filters.desc")}
              </span>
            </Button>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <label
            htmlFor={`${unavailableId}-from`}
            className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
          >
            {t("library.filters.valueFrom")}
          </label>
          <input
            id={`${unavailableId}-from`}
            type="text"
            inputMode="decimal"
            disabled
            placeholder={t("library.unavailable")}
            aria-describedby={unavailableId}
            className="h-9 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>
        <div className="space-y-1.5">
          <label
            htmlFor={`${unavailableId}-to`}
            className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
          >
            {t("library.filters.valueTo")}
          </label>
          <input
            id={`${unavailableId}-to`}
            type="text"
            inputMode="decimal"
            disabled
            placeholder={t("library.unavailable")}
            aria-describedby={unavailableId}
            className="h-9 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>
        <div className="space-y-1.5">
          <label
            htmlFor={`${unavailableId}-issuer`}
            className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground"
          >
            {t("library.filters.issuer")}
          </label>
          <input
            id={`${unavailableId}-issuer`}
            type="text"
            disabled
            placeholder={t("library.unavailable")}
            aria-describedby={unavailableId}
            className="h-9 w-full rounded-[6px] border border-border bg-surface px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <p
          id={unavailableId}
          className="flex max-w-2xl items-start gap-2 text-[0.65rem] leading-relaxed text-muted-foreground"
        >
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span>{t("library.filters.unavailable")}</span>
        </p>
        {hasActiveLibraryFilters(params) ? (
          <Button type="button" variant="ghost" size="sm" onClick={onClear}>
            {t("library.filters.clear")}
          </Button>
        ) : null}
      </div>
    </fieldset>
  );
}
