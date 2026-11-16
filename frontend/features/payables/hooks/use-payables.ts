"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiFetch,
  endpoints,
  payableListSchema,
  payableSchema,
  reminderPreferenceSchema,
  reminderPreferenceUpdateSchema,
} from "@/lib/api";
import type {
  Payable,
  PayableList,
  PayableStatus,
  ReminderPreference,
  ReminderPreferenceUpdate,
} from "@/lib/api/schemas";
import { queryKeys } from "@/lib/query/keys";

import type { PayableAction } from "@/lib/api/endpoints";

export type PayablesFilters = {
  status?: PayableStatus[];
  dueFrom?: string;
  dueTo?: string;
  limit?: number;
  cursor?: string | null;
  refetchOnWindowFocus?: boolean;
};

export function usePayables(filters: PayablesFilters = {}) {
  const normalizedParams = {
    status: filters.status ?? null,
    dueFrom: filters.dueFrom ?? null,
    dueTo: filters.dueTo ?? null,
    limit: filters.limit ?? null,
    cursor: filters.cursor ?? null,
  };

  return useQuery({
    queryKey: queryKeys.payables.list(normalizedParams),
    queryFn: () =>
      apiFetch<PayableList>(endpoints.payables.list, {
        schema: payableListSchema,
        query: {
          status: normalizedParams.status ?? undefined,
          due_from: normalizedParams.dueFrom ?? undefined,
          due_to: normalizedParams.dueTo ?? undefined,
          limit: normalizedParams.limit ?? undefined,
          cursor: normalizedParams.cursor ?? undefined,
        },
      }),
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: filters.refetchOnWindowFocus,
  });
}

export function useReminderPreferences() {
  return useQuery({
    queryKey: queryKeys.payables.reminderPreferences,
    queryFn: () =>
      apiFetch<ReminderPreference>(endpoints.payables.reminderPreferences, {
        schema: reminderPreferenceSchema,
      }),
  });
}

export function useUpdateReminderPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ReminderPreferenceUpdate) =>
      apiFetch<ReminderPreference>(endpoints.payables.reminderPreferences, {
        method: "PUT",
        schema: reminderPreferenceSchema,
        body: reminderPreferenceUpdateSchema.parse(input),
      }),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.payables.reminderPreferences });
      const previous = queryClient.getQueryData<ReminderPreference>(
        queryKeys.payables.reminderPreferences,
      );

      queryClient.setQueryData<ReminderPreference>(
        queryKeys.payables.reminderPreferences,
        (current) => ({
          offsets_days: input.offsets_days,
          local_time: input.local_time,
          channels: input.channels,
          timezone: current?.timezone ?? "UTC",
        }),
      );

      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.payables.reminderPreferences, context.previous);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.payables.reminderPreferences, data);
    },
  });
}

export function usePayableAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ payableId, action }: { payableId: string; action: PayableAction }) =>
      apiFetch<Payable>(endpoints.payables.action(payableId, action), {
        method: "POST",
        schema: payableSchema,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.payables.all }),
  });
}

export function useReschedulePayable() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ payableId, dueDate }: { payableId: string; dueDate: string }) =>
      apiFetch<Payable>(endpoints.payables.dueDate(payableId), {
        method: "PATCH",
        schema: payableSchema,
        body: { due_date: dueDate },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.payables.all }),
  });
}
