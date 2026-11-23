import { describe, expect, it } from "vitest";

import { authErrorKey, parseAuthProblem, readRetryAfter, toAuthErrorKind } from "./errors";

describe("toAuthErrorKind", () => {
  it("maps known codes", () => {
    expect(toAuthErrorKind("invalid_credentials")).toBe("invalid_credentials");
    expect(toAuthErrorKind("email_not_verified")).toBe("email_not_verified");
  });

  it("falls back to unknown for missing or foreign codes", () => {
    expect(toAuthErrorKind(null)).toBe("unknown");
    expect(toAuthErrorKind("password")).toBe("unknown");
  });
});

describe("authErrorKey", () => {
  it("returns dictionary keys for every kind", () => {
    expect(authErrorKey("invalid_credentials")).toBe("auth.errors.invalid_credentials");
    expect(authErrorKey("too_many_attempts")).toBe("auth.errors.too_many_attempts");
    expect(authErrorKey(undefined)).toBe("auth.errors.unknown");
  });
});

describe("parseAuthProblem", () => {
  it("reads code, retry and violations", () => {
    const problem = parseAuthProblem(
      { code: "too_many_attempts", retry_after: 45, violations: ["too_short", 7] },
      429,
    );

    expect(problem).toEqual({
      status: 429,
      code: "too_many_attempts",
      retryAfterSeconds: 45,
      violations: ["too_short"],
    });
  });

  it("tolerates malformed payloads", () => {
    expect(parseAuthProblem("nope", 500)).toEqual({
      status: 500,
      code: "unknown",
      retryAfterSeconds: null,
      violations: [],
    });
  });
});

describe("readRetryAfter", () => {
  it("parses the header", () => {
    const response = new Response(null, { status: 429, headers: { "Retry-After": "30" } });

    expect(readRetryAfter(response)).toBe(30);
  });

  it("ignores absent or invalid values", () => {
    expect(readRetryAfter(new Response(null, { status: 429 }))).toBeNull();

    const invalid = new Response(null, { status: 429, headers: { "Retry-After": "soon" } });
    expect(readRetryAfter(invalid)).toBeNull();
  });
});
