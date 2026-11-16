"use client";

import { Info, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo } from "react";

import { Button } from "@/components/ui/button";
import type { DataTableState } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  computeLibraryView,
  libraryHref,
  LIBRARY_MAX_SAMPLE,
  parseLibraryParams,
  type LibraryBand,
  type LibraryKind,
  type LibraryParams,
  type LibraryView,
} from "@/lib/analyses/library";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

import { useAnalysisLibrary } from "../hooks/use-analysis-library";
import { AnalysisLibraryTable } from "./analysis-library-table";
import { LibraryFilters } from "./library-filters";
import { LibraryPagination } from "./library-pagination";

type KindCopy = {
  eyebrow: TranslationKey;
  title: TranslationKey;
  description: TranslationKey;
  emptyTitle: TranslationKey;
  emptyDescription: TranslationKey;
};

const KIND_COPY: Record<LibraryKind, KindCopy> = {
  boleto: {
    eyebrow: "boletos.eyebrow",
    title: "boletos.title",
    description: "boletos.description",
    emptyTitle: "boletos.emptyTitle",
    emptyDescription: "boletos.emptyDescription",
  },
  payslip: {
    eyebrow: "folha.eyebrow",
    title: "folha.title",
    description: "folha.description",
    emptyTitle: "folha.emptyTitle",
    emptyDescription: "folha.emptyDescription",
  },
};

const BAND_TABS: readonly { value: LibraryBand; labelKey: TranslationKey }[] = [
  { value: "all", labelKey: "library.tabs.all" },
  { value: "low", labelKey: "risk.low" },
  { value: "attention", labelKey: "risk.attention" },
  { value: "high", labelKey: "risk.high" },
];

function countLabel(
  counts: LibraryView["counts"] | null,
  band: LibraryBand,
  truncated: boolean,
  pendingLabel: string,
): string {
  if (counts === null) {
    return pendingLabel;
  }

  const count = counts[band];

  return count > 0 && truncated ? `${count}+` : String(count);
}

export function AnalysisLibraryPage({ kind }: Readonly<{ kind: LibraryKind }>) {
  const { t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const params = useMemo(() => parseLibraryParams(new URLSearchParams(searchKey)), [searchKey]);
  const copy = KIND_COPY[kind];
  const query = useAnalysisLibrary(kind);
  const view = useMemo(
    () => (query.data ? computeLibraryView(query.data.items, kind, params, new Date()) : null),
    [kind, params, query.data],
  );
  const truncated = query.data?.truncated ?? false;
  const counts = view?.counts ?? null;
  const pendingCount = t("library.countPending");
  const firstLoad = query.isPending && !query.data;
  const errorWithoutData = query.isError && !query.data;
  const state: DataTableState = firstLoad
    ? "loading"
    : errorWithoutData
      ? "error"
      : view && view.total > 0
        ? "ready"
        : "empty";

  const updateParams = useCallback(
    (patch: Partial<LibraryParams>) => {
      const current = parseLibraryParams(new URLSearchParams(window.location.search));
      const next: LibraryParams = {
        ...current,
        ...patch,
        page: patch.page ?? 1,
      };

      router.replace(libraryHref(pathname, next), { scroll: false });
    },
    [pathname, router],
  );

  const clearFilters = useCallback(() => {
    router.replace(pathname, { scroll: false });
  }, [pathname, router]);

  useEffect(() => {
    if (view && view.page !== params.page) {
      router.replace(libraryHref(pathname, { ...params, page: view.page }), { scroll: false });
    }
  }, [params, pathname, router, view]);

  const emptyState =
    view && view.kindTotal === 0 ? (
      truncated ? (
        <EmptyState
          className="border-t-0 pt-0"
          title={t("library.emptySample.title")}
          description={t("library.emptySample.description", {
            count: query.data?.items.length ?? 0,
          })}
        />
      ) : (
        <EmptyState
          className="border-t-0 pt-0"
          title={t(copy.emptyTitle)}
          description={t(copy.emptyDescription)}
          action={{
            label: t("library.emptyTotal.action"),
            href: `/verificacao?tipo=${kind}`,
          }}
        />
      )
    ) : (
      <EmptyState
        className="border-t-0 pt-0"
        title={t("library.emptyFiltered.title")}
        description={t("library.emptyFiltered.description")}
        action={{
          label: t("library.emptyFiltered.action"),
          onClick: clearFilters,
        }}
      />
    );

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-border pb-6">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          {t(copy.eyebrow)}
        </p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <h1
              id="analysis-library-title"
              className="font-serif text-4xl leading-tight tracking-tight sm:text-5xl"
            >
              {t(copy.title)}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              {t(copy.description)}
            </p>
          </div>
          <Button asChild>
            <Link href={`/verificacao?tipo=${kind}`}>
              <Plus aria-hidden="true" />
              {t("library.newVerification")}
            </Link>
          </Button>
        </div>
      </header>

      <section aria-labelledby="analysis-library-title" className="mt-8 min-w-0">
        <Tabs
          value={params.band}
          onValueChange={(value) => updateParams({ band: value as LibraryBand })}
        >
          <TabsList
            aria-label={t("library.tabs.aria")}
            className="flex h-auto w-full flex-wrap justify-start gap-1 rounded-[6px] border border-border bg-surface p-1"
          >
            {BAND_TABS.map((tab) => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="gap-2 data-[state=active]:bg-surface-elevated data-[state=active]:text-foreground data-[state=active]:ring-1 data-[state=active]:ring-border"
              >
                <span>{t(tab.labelKey)}</span>
                <span className="font-mono text-[0.65rem] tabular-nums text-muted-foreground">
                  {countLabel(counts, tab.value, truncated, pendingCount)}
                </span>
              </TabsTrigger>
            ))}
          </TabsList>

          {BAND_TABS.map((tab) => (
            <TabsContent
              key={tab.value}
              value={tab.value}
              className="mt-4 space-y-4 text-sm leading-relaxed text-foreground"
            >
              <LibraryFilters params={params} onChange={updateParams} onClear={clearFilters} />

              {view && view.kindTotal > 0 ? (
                <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">
                  {truncated
                    ? t("library.note.truncated", { count: LIBRARY_MAX_SAMPLE })
                    : t("library.note.sample")}
                </p>
              ) : null}

              {view && view.activeCount > 0 ? (
                <p
                  role="status"
                  aria-live="polite"
                  className="flex items-center gap-2 text-xs text-muted-foreground"
                >
                  <Loader2
                    className="size-3.5 animate-spin motion-reduce:animate-none"
                    aria-hidden="true"
                  />
                  {t("library.note.active", { count: view.activeCount })}
                </p>
              ) : null}

              <p className="hidden items-center gap-2 text-xs text-muted-foreground md:flex">
                <Info className="size-3.5 shrink-0" aria-hidden="true" />
                {t("library.note.keyboard")}
              </p>

              <AnalysisLibraryTable
                kind={kind}
                view={view}
                state={state}
                emptyState={emptyState}
                onRetry={() => void query.refetch()}
              />

              {view && view.total > 0 ? (
                <LibraryPagination
                  page={view.page}
                  totalPages={view.totalPages}
                  total={view.total}
                  onPageChange={(page) => updateParams({ page })}
                />
              ) : null}
            </TabsContent>
          ))}
        </Tabs>
      </section>
    </div>
  );
}

export function AnalysisLibraryFallback() {
  const { t } = useI18n();

  return (
    <div
      className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8"
      aria-busy="true"
      role="status"
    >
      <span className="sr-only">{t("common.loading")}</span>
      <div className="space-y-3 border-b border-border pb-6">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-12 w-64 max-w-full" />
        <Skeleton className="h-4 w-full max-w-xl" />
      </div>
      <div className="mt-8 space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  );
}
