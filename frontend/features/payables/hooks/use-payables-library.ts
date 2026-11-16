"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch, endpoints, payableListSchema } from "@/lib/api";
import type { PayableList, PayableStatus } from "@/lib/api/schemas";
import {
  collectPayablePages,
  PAYMENTS_API_PAGE_SIZE,
  type PayableSample,
} from "@/lib/payables/library";
import { queryKeys } from "@/lib/query/keys";

export function usePayableSample(
  statuses: readonly PayableStatus[] | null,
  options: { enabled?: boolean } = {},
) {
  const normalizedStatuses = statuses ? [...statuses].sort() : null;

  return useQuery<PayableSample>({
    queryKey: queryKeys.payables.sample(normalizedStatuses),
    queryFn: () =>
      collectPayablePages((cursor) =>
        apiFetch<PayableList>(endpoints.payables.list, {
          schema: payableListSchema,
          query: {
            status: normalizedStatuses ?? undefined,
            limit: PAYMENTS_API_PAGE_SIZE,
            cursor: cursor ?? undefined,
          },
        }),
      ),
    staleTime: 15_000,
    refetchInterval: 300_000,
    refetchOnWindowFocus: true,
    enabled: options.enabled ?? true,
  });
}
