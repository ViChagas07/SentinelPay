import { afterEach, describe, expect, it, vi } from "vitest";

import { getSupportUrl } from "./organization";

describe("getSupportUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("accepts http and https urls", () => {
    vi.stubEnv("NEXT_PUBLIC_SUPPORT_URL", "https://support.example.test");
    expect(getSupportUrl()).toBe("https://support.example.test/");

    vi.stubEnv("NEXT_PUBLIC_SUPPORT_URL", "http://support.example.test/help");
    expect(getSupportUrl()).toBe("http://support.example.test/help");
  });

  it("rejects empty, invalid and non-http urls", () => {
    vi.stubEnv("NEXT_PUBLIC_SUPPORT_URL", "");
    expect(getSupportUrl()).toBeNull();

    vi.stubEnv("NEXT_PUBLIC_SUPPORT_URL", "not-a-url");
    expect(getSupportUrl()).toBeNull();

    vi.stubEnv("NEXT_PUBLIC_SUPPORT_URL", "javascript:alert(1)");
    expect(getSupportUrl()).toBeNull();
  });
});
