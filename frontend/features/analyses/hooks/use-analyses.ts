"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  analysisDetailSchema,
  analysisListSchema,
  apiFetch,
  createAnalysisResponseSchema,
  endpoints,
} from "@/lib/api";
import type {
  AnalysisDetail,
  AnalysisKind,
  AnalysisList,
  CreateAnalysisResponse,
} from "@/lib/api/schemas";
import { queryKeys } from "@/lib/query/keys";

export type AnalysesQuery = {
  limit?: number;
  cursor?: string | null;
  refetchOnWindowFocus?: boolean;
};

export type CreateAnalysisInput = {
  file: File;
  kind: AnalysisKind;
  idempotencyKey?: string;
};

export function useAnalyses(params: AnalysesQuery = {}) {
  const normalizedParams = {
    limit: params.limit ?? null,
    cursor: params.cursor ?? null,
  };

  return useQuery({
    queryKey: queryKeys.analyses.list(normalizedParams),
    queryFn: () =>
      apiFetch<AnalysisList>(endpoints.analyses.list, {
        schema: analysisListSchema,
        query: {
          limit: normalizedParams.limit ?? undefined,
          cursor: normalizedParams.cursor ?? undefined,
        },
      }),
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: params.refetchOnWindowFocus,
  });
}

export function useAnalysis(analysisId: string | null | undefined) {
  const id = analysisId ?? "";

  return useQuery({
    queryKey: queryKeys.analyses.detail(id),
    queryFn: () =>
      apiFetch<AnalysisDetail>(endpoints.analyses.detail(id), {
        schema: analysisDetailSchema,
      }),
    enabled: id.length > 0,
    retry: false,
  });
}

export function useCreateAnalysis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, kind, idempotencyKey }: CreateAnalysisInput) => {
      const formData = new FormData();
      formData.set("kind", kind);
      formData.set("file", file);

      return apiFetch<CreateAnalysisResponse>(endpoints.analyses.create, {
        method: "POST",
        schema: createAnalysisResponseSchema,
        formData,
        idempotencyKey,
      });
    },
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.analyses.all,
      }),
  });
}
