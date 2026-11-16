"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch, endpoints, userProfileSchema } from "@/lib/api";
import type { UserProfile } from "@/lib/api/schemas";
import { queryKeys } from "@/lib/query/keys";

type UseMeOptions = {
  enabled?: boolean;
};

export function useMe(options: UseMeOptions = {}) {
  return useQuery({
    queryKey: queryKeys.users.me,
    queryFn: () =>
      apiFetch<UserProfile>(endpoints.users.me, {
        schema: userProfileSchema,
      }),
    enabled: options.enabled ?? true,
    retry: false,
  });
}
