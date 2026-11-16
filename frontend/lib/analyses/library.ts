import type { AnalysisListItem, AnalysisList, AnalysisStatus, RiskBand } from "@/lib/api/schemas";

export type LibraryKind = "boleto" | "payslip";

export const LIBRARY_BANDS = ["all", "low", "attention", "high"] as const;
export const LIBRARY_STATUS_FILTERS = ["all", "active", "done", "failed"] as const;
export const LIBRARY_PERIODS = ["all", 7, 30, 90, 365] as const;
export const LIBRARY_SORTS = ["date", "score"] as const;
export const LIBRARY_DIRECTIONS = ["asc", "desc"] as const;

export type LibraryBand = (typeof LIBRARY_BANDS)[number];
export type LibraryStatusFilter = (typeof LIBRARY_STATUS_FILTERS)[number];
export type LibraryPeriod = (typeof LIBRARY_PERIODS)[number];
export type LibrarySort = (typeof LIBRARY_SORTS)[number];
export type LibraryDirection = (typeof LIBRARY_DIRECTIONS)[number];

export type LibraryParams = {
  band: LibraryBand;
  status: LibraryStatusFilter;
  period: LibraryPeriod;
  query: string;
  sort: LibrarySort;
  direction: LibraryDirection;
  page: number;
};

export type LibraryCounts = Record<RiskBand, number> & { all: number };

export type LibraryView = {
  kindTotal: number;
  activeCount: number;
  counts: LibraryCounts;
  items: AnalysisListItem[];
  total: number;
  page: number;
  totalPages: number;
};

export type AnalysisLibraryDataset = {
  items: AnalysisListItem[];
  truncated: boolean;
  fetchedAt: string;
};

export const LIBRARY_PAGE_SIZE = 10;
export const LIBRARY_API_PAGE_SIZE = 50;
export const LIBRARY_MAX_PAGES = 10;
export const LIBRARY_MAX_SAMPLE = LIBRARY_API_PAGE_SIZE * LIBRARY_MAX_PAGES;
export const LIBRARY_MAX_QUERY_LENGTH = 64;

const DAY_MS = 86_400_000;

export const DEFAULT_LIBRARY_PARAMS: LibraryParams = {
  band: "all",
  status: "all",
  period: "all",
  query: "",
  sort: "date",
  direction: "desc",
  page: 1,
};

function readEnum<T extends string>(value: string | null, allowed: readonly T[], fallback: T): T {
  return value !== null && (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
}

function readPeriod(value: string | null): LibraryPeriod {
  if (value === null) {
    return "all";
  }

  const days = Number(value);

  return (LIBRARY_PERIODS as readonly (string | number)[]).includes(days)
    ? (days as LibraryPeriod)
    : "all";
}

function readPage(value: string | null): number {
  const page = Number.parseInt(value ?? "1", 10);

  return Number.isFinite(page) && page > 0 ? page : 1;
}

export function parseLibraryParams(search: URLSearchParams): LibraryParams {
  return {
    band: readEnum(search.get("band"), LIBRARY_BANDS, DEFAULT_LIBRARY_PARAMS.band),
    status: readEnum(search.get("status"), LIBRARY_STATUS_FILTERS, DEFAULT_LIBRARY_PARAMS.status),
    period: readPeriod(search.get("period")),
    query: (search.get("q") ?? "").trim().slice(0, LIBRARY_MAX_QUERY_LENGTH),
    sort: readEnum(search.get("sort"), LIBRARY_SORTS, DEFAULT_LIBRARY_PARAMS.sort),
    direction: readEnum(search.get("dir"), LIBRARY_DIRECTIONS, DEFAULT_LIBRARY_PARAMS.direction),
    page: readPage(search.get("page")),
  };
}

export function serializeLibraryParams(params: LibraryParams): URLSearchParams {
  const search = new URLSearchParams();

  if (params.band !== DEFAULT_LIBRARY_PARAMS.band) {
    search.set("band", params.band);
  }

  if (params.status !== DEFAULT_LIBRARY_PARAMS.status) {
    search.set("status", params.status);
  }

  if (params.period !== DEFAULT_LIBRARY_PARAMS.period) {
    search.set("period", String(params.period));
  }

  if (params.query.length > 0) {
    search.set("q", params.query);
  }

  if (params.sort !== DEFAULT_LIBRARY_PARAMS.sort) {
    search.set("sort", params.sort);
  }

  if (params.direction !== DEFAULT_LIBRARY_PARAMS.direction) {
    search.set("dir", params.direction);
  }

  if (params.page > 1) {
    search.set("page", String(params.page));
  }

  return search;
}

export function libraryHref(pathname: string, params: LibraryParams): string {
  const search = serializeLibraryParams(params).toString();

  return search.length > 0 ? `${pathname}?${search}` : pathname;
}

export function hasActiveLibraryFilters(params: LibraryParams): boolean {
  return (
    params.band !== DEFAULT_LIBRARY_PARAMS.band ||
    params.status !== DEFAULT_LIBRARY_PARAMS.status ||
    params.period !== DEFAULT_LIBRARY_PARAMS.period ||
    params.query.length > 0 ||
    params.sort !== DEFAULT_LIBRARY_PARAMS.sort ||
    params.direction !== DEFAULT_LIBRARY_PARAMS.direction
  );
}

export function statusGroupOf(status: AnalysisStatus): Exclude<LibraryStatusFilter, "all"> {
  if (status === "failed") {
    return "failed";
  }

  if (status === "completed" || status === "degraded") {
    return "done";
  }

  return "active";
}

export function periodStart(period: LibraryPeriod, now: Date): Date | null {
  if (period === "all") {
    return null;
  }

  return new Date(now.getTime() - period * DAY_MS);
}

export function matchesLibraryQuery(item: AnalysisListItem, query: string): boolean {
  const normalized = query.trim().toLowerCase().replace(/^#+/, "").replace(/-/g, "");

  if (normalized.length === 0) {
    return true;
  }

  return item.id.toLowerCase().replace(/-/g, "").includes(normalized);
}

function matchesBaseFilters(
  item: AnalysisListItem,
  kind: LibraryKind,
  params: LibraryParams,
  now: Date,
): boolean {
  if (item.kind !== kind) {
    return false;
  }

  if (params.status !== "all" && statusGroupOf(item.status) !== params.status) {
    return false;
  }

  if (!matchesLibraryQuery(item, params.query)) {
    return false;
  }

  const start = periodStart(params.period, now);

  if (start !== null) {
    const createdAt = new Date(item.created_at).getTime();

    if (Number.isNaN(createdAt) || createdAt < start.getTime()) {
      return false;
    }
  }

  return true;
}

function compareByDateAsc(left: AnalysisListItem, right: AnalysisListItem): number {
  const leftTime = new Date(left.created_at).getTime();
  const rightTime = new Date(right.created_at).getTime();

  return leftTime - rightTime || left.id.localeCompare(right.id);
}

export function sortLibraryItems(
  items: readonly AnalysisListItem[],
  sort: LibrarySort,
  direction: LibraryDirection,
): AnalysisListItem[] {
  const factor = direction === "asc" ? 1 : -1;

  return [...items].sort((left, right) => {
    if (sort === "score") {
      if (left.score === null && right.score === null) {
        return -compareByDateAsc(left, right);
      }

      if (left.score === null) {
        return 1;
      }

      if (right.score === null) {
        return -1;
      }

      return (left.score - right.score) * factor || -compareByDateAsc(left, right);
    }

    return compareByDateAsc(left, right) * factor;
  });
}

export function computeLibraryView(
  items: readonly AnalysisListItem[],
  kind: LibraryKind,
  params: LibraryParams,
  now: Date,
  pageSize: number = LIBRARY_PAGE_SIZE,
): LibraryView {
  const kindItems = items.filter((item) => item.kind === kind);
  const baseItems = kindItems.filter((item) => matchesBaseFilters(item, kind, params, now));
  const counts: LibraryCounts = {
    all: baseItems.length,
    low: baseItems.filter((item) => item.band === "low").length,
    attention: baseItems.filter((item) => item.band === "attention").length,
    high: baseItems.filter((item) => item.band === "high").length,
  };
  const bandItems =
    params.band === "all" ? baseItems : baseItems.filter((item) => item.band === params.band);
  const sorted = sortLibraryItems(bandItems, params.sort, params.direction);
  const safePageSize = Math.max(1, Math.trunc(pageSize));
  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / safePageSize));
  const page = Math.min(Math.max(1, Math.trunc(params.page)), totalPages);
  const start = (page - 1) * safePageSize;

  return {
    kindTotal: kindItems.length,
    activeCount: baseItems.filter((item) => statusGroupOf(item.status) === "active").length,
    counts,
    items: sorted.slice(start, start + safePageSize),
    total,
    page,
    totalPages,
  };
}

export async function collectAnalysisPages(
  loadPage: (cursor: string | null) => Promise<AnalysisList>,
  options: { maxPages?: number; now?: () => string } = {},
): Promise<AnalysisLibraryDataset> {
  const maxPages = Math.max(1, Math.trunc(options.maxPages ?? LIBRARY_MAX_PAGES));
  const items: AnalysisListItem[] = [];
  let cursor: string | null = null;
  let pages = 0;

  while (pages < maxPages) {
    const page = await loadPage(cursor);

    items.push(...page.items);
    pages += 1;

    if (page.next_cursor === null || page.items.length === 0) {
      cursor = page.next_cursor;
      break;
    }

    cursor = page.next_cursor;
  }

  return {
    items,
    truncated: cursor !== null,
    fetchedAt: options.now ? options.now() : new Date().toISOString(),
  };
}
