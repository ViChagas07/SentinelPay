import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/errors";

const MAX_RATE_LIMIT_WAIT_SECONDS = 60;

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      const wait = error.retryAfterSeconds;

      if (wait === null) {
        return false;
      }

      return failureCount < 1 && wait <= MAX_RATE_LIMIT_WAIT_SECONDS;
    }

    if (error.status >= 400 && error.status < 500) {
      return false;
    }
  }

  return failureCount < 2;
}

export function queryRetryDelay(failureCount: number, error: unknown): number {
  if (error instanceof ApiError && error.status === 429 && error.retryAfterSeconds !== null) {
    return Math.min(error.retryAfterSeconds, MAX_RATE_LIMIT_WAIT_SECONDS) * 1_000;
  }

  return Math.min(1_000 * 2 ** failureCount, 30_000);
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: shouldRetryQuery,
        retryDelay: queryRetryDelay,
      },
      mutations: {
        retry: false,
      },
    },
  });
}
