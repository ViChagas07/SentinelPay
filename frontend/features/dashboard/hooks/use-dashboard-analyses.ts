"use client";

import { useQuery } from "@tanstack/react-query";

import { analysisListSchema, apiFetch, endpoints } from "@/lib/api";
import type { AnalysisList, AnalysisListItem } from "@/lib/api/schemas";
import { queryKeys } from "@/lib/query/keys";

const PAGE_SIZE = 50;
const MAX_PAGES = 10;
const DAY_MS = 86_400_000;

export type DashboardAnalysesData = {
  items: AnalysisListItem[];
  fetchedAt: string;
  truncated: boolean;
};

async function fetchAnalysesWindow(periodDays: number): Promise<DashboardAnalysesData> {
  const fetchedAt = new Date();
  const cutoff = fetchedAt.getTime() - Math.max(1, periodDays) * 2 * DAY_MS;
  const items: AnalysisListItem[] = [];
  let cursor: string | null = null;
  let pages = 0;
  let complete = false;

  do {
    const page: AnalysisList = await apiFetch<AnalysisList>(endpoints.analyses.list, {
      schema: analysisListSchema,
      query: {
        limit: PAGE_SIZE,
        cursor: cursor ?? undefined,
      },
    });

    items.push(...page.items);
    cursor = page.next_cursor;
    pages += 1;

    const oldest = page.items.at(-1);

    if (!oldest) {
      complete = true;
      break;
    }

    if (new Date(oldest.created_at).getTime() < cutoff) {
      complete = true;
      break;
    }
  } while (cursor !== null && pages < MAX_PAGES);

  if (cursor === null) {
    complete = true;
  }

  return {
    items,
    fetchedAt: fetchedAt.toISOString(),
    truncated: !complete,
  };
}

export function useDashboardAnalyses(periodDays: number) {
  return useQuery({
    queryKey: queryKeys.dashboard.analyses(periodDays),
    queryFn: () => fetchAnalysesWindow(periodDays),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    retry: 1,
  });
}
