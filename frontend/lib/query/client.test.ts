import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/errors";

import { queryRetryDelay, shouldRetryQuery } from "./client";

function apiError(status: number, retryAfterSeconds: number | null = null): ApiError {
  return new ApiError({
    status,
    code: "test",
    title: "Test",
    detail: "Test",
    retryAfterSeconds,
  });
}

describe("query retry policy", () => {
  it("does not retry client errors other than 429", () => {
    expect(shouldRetryQuery(0, apiError(401))).toBe(false);
    expect(shouldRetryQuery(0, apiError(403))).toBe(false);
    expect(shouldRetryQuery(0, apiError(404))).toBe(false);
  });

  it("retries 429 once when Retry-After is short", () => {
    expect(shouldRetryQuery(0, apiError(429, 12))).toBe(true);
    expect(shouldRetryQuery(1, apiError(429, 12))).toBe(false);
  });

  it("does not retry 429 when Retry-After is missing or too long", () => {
    expect(shouldRetryQuery(0, apiError(429, null))).toBe(false);
    expect(shouldRetryQuery(0, apiError(429, 120))).toBe(false);
  });

  it("waits for Retry-After before retrying a 429", () => {
    expect(queryRetryDelay(0, apiError(429, 12))).toBe(12_000);
    expect(queryRetryDelay(0, apiError(429, 120))).toBe(60_000);
  });

  it("keeps exponential backoff for transient failures", () => {
    expect(queryRetryDelay(0, apiError(500))).toBe(1_000);
    expect(queryRetryDelay(1, apiError(500))).toBe(2_000);
    expect(shouldRetryQuery(0, apiError(500))).toBe(true);
    expect(shouldRetryQuery(2, apiError(500))).toBe(false);
  });
});
