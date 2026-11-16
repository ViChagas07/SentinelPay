"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useRef } from "react";

import { analysisListSchema, apiFetch, endpoints } from "@/lib/api";
import type { AnalysisList } from "@/lib/api/schemas";
import {
  collectAnalysisPages,
  LIBRARY_API_PAGE_SIZE,
  type AnalysisLibraryDataset,
  type LibraryKind,
} from "@/lib/analyses/library";
import { queryKeys } from "@/lib/query/keys";
import { isActiveStatus, pollIntervalFor } from "@/lib/verification/polling";

export function useAnalysisLibrary(kind: LibraryKind) {
  const activeSinceRef = useRef<number | null>(null);

  return useQuery<AnalysisLibraryDataset>({
    queryKey: queryKeys.analyses.library,
    queryFn: () =>
      collectAnalysisPages((cursor) =>
        apiFetch<AnalysisList>(endpoints.analyses.list, {
          schema: analysisListSchema,
          query: {
            limit: LIBRARY_API_PAGE_SIZE,
            cursor: cursor ?? undefined,
          },
        }),
      ),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
    retry: 1,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const hasActiveJob = items.some((item) => item.kind === kind && isActiveStatus(item.status));

      if (!hasActiveJob) {
        activeSinceRef.current = null;
        return false;
      }

      if (activeSinceRef.current === null) {
        activeSinceRef.current = Date.now();
      }

      return pollIntervalFor("processing", Date.now() - activeSinceRef.current);
    },
  });
}
