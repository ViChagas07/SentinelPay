import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { apiFetch } from "./client";
import { ApiError } from "./errors";
import { configureApiInterceptors, resetApiInterceptors } from "./interceptors";
import { setApiLocale } from "./locale";

function jsonResponse(body: unknown, status = 200, headers?: HeadersInit): Response {
  const responseHeaders = new Headers(headers);
  responseHeaders.set("content-type", "application/json");
  return new Response(JSON.stringify(body), { status, headers: responseHeaders });
}

function problemResponse(status: number, code: string, headers?: HeadersInit): Response {
  const responseHeaders = new Headers(headers);
  responseHeaders.set("content-type", "application/problem+json");

  return new Response(
    JSON.stringify({
      type: "https://paysentineliq.local/problems/test",
      title: "Test problem",
      status,
      detail: "Test detail",
      instance: "/api/v1/test",
      code,
      request_id: "req-1",
    }),
    { status, headers: responseHeaders },
  );
}

const payloadSchema = z.object({ value: z.string() });

describe("apiFetch", () => {
  beforeEach(() => {
    setApiLocale(undefined);
    resetApiInterceptors();
    vi.stubGlobal("location", { origin: "http://localhost:3000" });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses a valid same-origin response and sends credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ value: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/test", { schema: payloadSchema })).resolves.toEqual({
      value: "ok",
    });

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe("http://localhost:3000/api/v1/test");
    expect(init).toMatchObject({ credentials: "include", cache: "no-store" });
  });

  it("never sends an authorization header from the browser", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ value: "ok" }));
    vi.stubGlobal("fetch", fetchMock);
    setApiLocale("pt-BR");

    await apiFetch("/api/v1/test", { schema: payloadSchema });

    const [, init] = fetchMock.mock.calls[0] ?? [];
    const headers = new Headers(init?.headers);
    expect(headers.has("Authorization")).toBe(false);
    expect(headers.get("Accept-Language")).toBe("pt-BR");
  });

  it("serializes repeated query parameters and skips nulls", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ value: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/test", {
      schema: payloadSchema,
      query: { status: ["pending", "paid"], limit: 20, cursor: null },
    });

    const [url] = fetchMock.mock.calls[0] ?? [];
    expect(url).toContain("status=pending&status=paid");
    expect(url).toContain("limit=20");
    expect(url).not.toContain("cursor");
  });

  it("sends multipart form data without a JSON content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ value: "ok" }));
    vi.stubGlobal("fetch", fetchMock);
    const formData = new FormData();
    formData.set("kind", "boleto");

    await apiFetch("/api/v1/analyses", {
      method: "POST",
      schema: payloadSchema,
      formData,
    });

    const [, init] = fetchMock.mock.calls[0] ?? [];
    const headers = new Headers(init?.headers);
    expect(init?.body).toBe(formData);
    expect(headers.has("Content-Type")).toBe(false);
  });

  it("standardizes 401 and notifies the unauthorized interceptor", async () => {
    const fetchMock = vi.fn().mockResolvedValue(problemResponse(401, "invalid_access_token"));
    vi.stubGlobal("fetch", fetchMock);
    const onUnauthorized = vi.fn();
    configureApiInterceptors({ onUnauthorized });

    await expect(apiFetch("/api/v1/test", { schema: payloadSchema })).rejects.toMatchObject({
      status: 401,
      code: "invalid_access_token",
      requestId: "req-1",
    });
    expect(onUnauthorized).toHaveBeenCalledWith(expect.any(ApiError));
  });

  it("standardizes 403 and notifies the forbidden interceptor", async () => {
    const fetchMock = vi.fn().mockResolvedValue(problemResponse(403, "forbidden"));
    vi.stubGlobal("fetch", fetchMock);
    const onForbidden = vi.fn();
    configureApiInterceptors({ onForbidden });

    await expect(apiFetch("/api/v1/test", { schema: payloadSchema })).rejects.toMatchObject({
      status: 403,
      code: "forbidden",
    });
    expect(onForbidden).toHaveBeenCalledTimes(1);
  });

  it("preserves retry-after seconds from 429 responses and notifies the rate limit interceptor", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(problemResponse(429, "rate_limited", { "retry-after": "12" }));
    vi.stubGlobal("fetch", fetchMock);
    const onRateLimited = vi.fn();
    configureApiInterceptors({ onRateLimited });

    await expect(apiFetch("/api/v1/test", { schema: payloadSchema })).rejects.toMatchObject({
      status: 429,
      code: "rate_limited",
      retryAfterSeconds: 12,
    });
    expect(onRateLimited).toHaveBeenCalledWith(expect.any(ApiError));
  });

  it("rejects responses that do not match the schema", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ value: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/test", { schema: payloadSchema })).rejects.toMatchObject({
      status: 200,
      code: "response_schema_invalid",
    });
  });

  it("returns undefined for 204 responses without a schema", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("converts network failures to a standardized error", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("network down"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/test", { schema: payloadSchema })).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });
});
