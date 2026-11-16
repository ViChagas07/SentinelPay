"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback } from "react";

import { apiFetch, endpoints, userProfileSchema } from "@/lib/api";
import { isUnauthorizedError } from "@/lib/api/errors";
import type { UserProfile } from "@/lib/api/schemas";
import { queryKeys } from "@/lib/query/keys";
import { buildLoginPath } from "@/lib/session/client";

export type SessionStatus = "loading" | "authenticated" | "anonymous";

export type SessionState = {
  user: UserProfile | null;
  status: SessionStatus;
  error: unknown;
  refresh: () => Promise<void>;
  logout: () => Promise<boolean>;
};

export function useSession(initialUser?: UserProfile | null): SessionState {
  const queryClient = useQueryClient();
  const router = useRouter();

  const query = useQuery({
    queryKey: queryKeys.users.me,
    queryFn: () =>
      apiFetch<UserProfile>(endpoints.users.me, {
        schema: userProfileSchema,
      }),
    retry: false,
    staleTime: 60_000,
    initialData: initialUser ?? undefined,
  });

  const refresh = useCallback(async () => {
    await query.refetch();
  }, [query]);

  const logout = useCallback(async () => {
    let ok = true;

    try {
      const response = await fetch("/api/v1/auth/logout", {
        method: "POST",
        credentials: "include",
        cache: "no-store",
      });

      ok = response.ok || response.status === 401;
    } catch {
      ok = false;
    }

    queryClient.clear();
    router.replace(buildLoginPath({}));
    router.refresh();

    return ok;
  }, [queryClient, router]);

  const isUnauthorized = isUnauthorizedError(query.error);

  const status: SessionStatus = query.isPending
    ? "loading"
    : query.data
      ? "authenticated"
      : isUnauthorized
        ? "anonymous"
        : query.isError
          ? "anonymous"
          : "loading";

  return {
    user: query.data ?? null,
    status,
    error: query.error,
    refresh,
    logout,
  };
}
