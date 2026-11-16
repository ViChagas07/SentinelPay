import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { resetApiInterceptors } from "@/lib/api";

import { useUnreadCount } from "./use-notifications";

function createWrapper(client: QueryClient) {
  return function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("useUnreadCount", () => {
  afterEach(() => {
    resetApiInterceptors();
    vi.unstubAllGlobals();
  });

  it("loads the unread count from the same-origin BFF", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ unread: 4 }));
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { result } = renderHook(() => useUnreadCount(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ unread: 4 });

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain("/api/v1/notifications/unread-count");
    expect(init).toMatchObject({ credentials: "include" });
  });
});
