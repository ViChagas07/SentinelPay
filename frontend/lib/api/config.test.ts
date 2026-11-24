import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiConfigurationError,
  buildBackendUrl,
  getInternalApiBaseUrl,
  normalizeBaseUrl,
} from "@/lib/api/config";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("normalizeBaseUrl", () => {
  it("adds https to a host without a scheme", () => {
    expect(normalizeBaseUrl("sentinelpay.up.railway.app")).toBe(
      "https://sentinelpay.up.railway.app",
    );
  });

  it("keeps http for local hosts without a scheme", () => {
    expect(normalizeBaseUrl("localhost:8000")).toBe("http://localhost:8000");
    expect(normalizeBaseUrl("127.0.0.1:8000")).toBe("http://127.0.0.1:8000");
  });

  it("removes surrounding quotes and trailing slashes", () => {
    expect(normalizeBaseUrl('  "https://api.example.com/"  ')).toBe("https://api.example.com");
    expect(normalizeBaseUrl("'https://api.example.com/v1/'")).toBe(
      "https://api.example.com/v1",
    );
  });

  it("removes an accidental /api/v1 suffix because buildBackendUrl adds it", () => {
    expect(normalizeBaseUrl("https://api.example.com/api/v1")).toBe("https://api.example.com");
    expect(normalizeBaseUrl("https://api.example.com/api/v1/")).toBe("https://api.example.com");
  });

  it("rejects non http schemes, query strings and hashes", () => {
    expect(normalizeBaseUrl("ftp://api.example.com")).toBeNull();
    expect(normalizeBaseUrl("https://api.example.com?token=1")).toBeNull();
    expect(normalizeBaseUrl("https://api.example.com#fragment")).toBeNull();
    expect(normalizeBaseUrl("${{RAILWAY_PUBLIC_DOMAIN}}")).toBeNull();
    expect(normalizeBaseUrl("   ")).toBeNull();
  });
});

describe("buildBackendUrl", () => {
  it("builds an absolute URL from a scheme-less production value", () => {
    vi.stubEnv("API_INTERNAL_URL", "sentinelpay.up.railway.app");
    vi.stubEnv("NODE_ENV", "production");

    expect(buildBackendUrl("/api/v1/auth/google/login")).toBe(
      "https://sentinelpay.up.railway.app/api/v1/auth/google/login",
    );
  });

  it("returns an empty base and throws a typed error when production has no value", () => {
    vi.stubEnv("API_INTERNAL_URL", "");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "production");

    expect(getInternalApiBaseUrl()).toBe("");
    expect(() => buildBackendUrl("/api/v1/auth/google/login")).toThrow(ApiConfigurationError);
  });

  it("keeps the local default outside production", () => {
    vi.stubEnv("API_INTERNAL_URL", "");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "development");

    expect(buildBackendUrl("/api/v1/auth/google/login")).toBe(
      "http://localhost:8000/api/v1/auth/google/login",
    );
  });
});
