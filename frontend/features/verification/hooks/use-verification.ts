"use client";

import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  analysisDetailSchema,
  analysisListSchema,
  ApiError,
  apiFetch,
  cancelAnalysisResponseSchema,
  endpoints,
  type CancelAnalysisResponse,
} from "@/lib/api";
import type { AnalysisDetail, AnalysisList, AnalysisStatus } from "@/lib/api/schemas";
import { queryKeys } from "@/lib/query/keys";
import { createAnalysisStream } from "@/lib/verification/events";
import {
  elapsedBetween,
  isActiveStatus,
  isTerminalStatus,
  pollIntervalFor,
} from "@/lib/verification/polling";
import type { AnalysisStreamState } from "@/lib/verification/progress";

export type AnalysisJobResult = UseQueryResult<AnalysisDetail> & {
  streamState: AnalysisStreamState;
};

function hasActiveItem(items: readonly { status: AnalysisStatus }[]): boolean {
  return items.some((item) => isActiveStatus(item.status));
}

export function useAnalysisJob(analysisId: string | null | undefined): AnalysisJobResult {
  const id = analysisId ?? "";
  const queryClient = useQueryClient();
  const [streamState, setStreamState] = useState<AnalysisStreamState>(
    id.length > 0 ? "connecting" : "closed",
  );
  const key = useMemo(() => queryKeys.analyses.detail(id), [id]);

  const query = useQuery({
    queryKey: key,
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
    refetchInterval: (current) => {
      if (current.state.status === "error") {
        const error = current.state.error;

        if (
          error instanceof ApiError &&
          (error.status === 401 || error.status === 403 || error.status === 404)
        ) {
          return false;
        }

        return streamState === "polling" ? 5000 : false;
      }

      const data = current.state.data;

      if (!data) {
        return streamState === "polling" ? 2500 : false;
      }

      if (isTerminalStatus(data.status)) {
        return false;
      }

      if (streamState !== "polling") {
        return false;
      }

      return pollIntervalFor(data.status, elapsedBetween(data.created_at));
    },
  });

  const status = query.data?.status;
  const terminal = status !== undefined && isTerminalStatus(status);
  const refetch = query.refetch;

  useEffect(() => {
    if (id.length === 0 || terminal) {
      return;
    }

    const stream = createAnalysisStream({
      url: endpoints.analyses.events(id),
      onStateChange: setStreamState,
      onEvent: (event) => {
        queryClient.setQueryData<AnalysisDetail>(key, (current) => ({
          id: event.id,
          status: event.status,
          kind: event.kind,
          created_at: event.created_at,
          updated_at: event.updated_at,
          error_code: event.error_code,
          result_available: event.result_available,
          result: current?.result ?? null,
          progress: event.progress,
          cancelled_at: event.cancelled_at,
        }));

        if (isTerminalStatus(event.status)) {
          void queryClient.invalidateQueries({ queryKey: key });
        }
      },
    });

    return () => {
      stream.close();
    };
  }, [id, key, queryClient, terminal]);

  useEffect(() => {
    if (streamState === "polling") {
      void refetch();
    }
  }, [refetch, streamState]);

  return {
    ...query,
    streamState: id.length === 0 || terminal ? "closed" : streamState,
  };
}

export function useCancelAnalysis(analysisId: string | null | undefined) {
  const id = analysisId ?? "";
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiFetch<CancelAnalysisResponse>(endpoints.analyses.cancel(id), {
        method: "POST",
        schema: cancelAnalysisResponseSchema,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData<AnalysisDetail>(queryKeys.analyses.detail(id), (current) =>
        current === undefined ? current : { ...current, status: data.status },
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.analyses.detail(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.analyses.all });
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
