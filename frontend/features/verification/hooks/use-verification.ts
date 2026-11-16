"use client";

import { useQuery } from "@tanstack/react-query";

import { analysisDetailSchema, analysisListSchema, ApiError, apiFetch, endpoints } from "@/lib/api";
import type { AnalysisDetail, AnalysisList, AnalysisStatus } from "@/lib/api/schemas";
import { queryKeys } from "@/lib/query/keys";
import { elapsedBetween, isActiveStatus, pollIntervalFor } from "@/lib/verification/polling";

function hasActiveItem(items: readonly { status: AnalysisStatus }[]): boolean {
  return items.some((item) => isActiveStatus(item.status));
}

export function useAnalysisJob(analysisId: string | null | undefined) {
  const id = analysisId ?? "";

  return useQuery({
    queryKey: queryKeys.analyses.detail(id),
    queryFn: () =>
      apiFetch<AnalysisDetail>(endpoints.analyses.detail(id), {
        schema: analysisDetailSchema,
      }),
    enabled: id.length > 0,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
        return false;
      }

      return failureCount < 2;
    },
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      if (query.state.status === "error") {
        return false;
      }

      const data = query.state.data;

      if (!data) {
        return 2500;
      }

      return pollIntervalFor(data.status, elapsedBetween(data.created_at));
    },
  });
}

export function useRecentVerifications(limit = 6) {
  return useQuery({
    queryKey: queryKeys.analyses.list({ limit, cursor: null, source: "verification" }),
    queryFn: () =>
      apiFetch<AnalysisList>(endpoints.analyses.list, {
        schema: analysisListSchema,
        query: { limit },
      }),
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const data = query.state.data;

      if (!data) {
        return false;
      }

      return hasActiveItem(data.items) ? 5000 : false;
    },
  });
}
