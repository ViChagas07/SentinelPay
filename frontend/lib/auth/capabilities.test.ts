import { describe, expect, it, vi } from "vitest";

import { fetchAuthCapabilities, fetchPasswordPolicy } from "./capabilities";

vi.mock("@/lib/api/config", () => ({
  buildBackendUrl: (path: string) => `http://api.test${path}`,
}));

describe("fetchAuthCapabilities", () => {
  it("reads the back-end feature flags", async () => {
    const fetchImpl = vi.fn(async () =>
      Response.json({
        password_enabled: true,
        signup_enabled: true,
        password_reset_enabled: true,
        google_enabled: true,
      }),
    );

    await expect(fetchAuthCapabilities(fetchImpl as unknown as typeof fetch)).resolves.toEqual({
      passwordEnabled: true,
      signupEnabled: true,
      passwordResetEnabled: true,
      googleEnabled: true,
    });
  });

  it("keeps sign-up off when the back-end has no e-mail provider", async () => {
    const fetchImpl = vi.fn(async () =>
      Response.json({
        password_enabled: true,
        signup_enabled: false,
        password_reset_enabled: false,
        google_enabled: true,
      }),
    );

    await expect(fetchAuthCapabilities(fetchImpl as unknown as typeof fetch)).resolves.toEqual({
      passwordEnabled: true,
      signupEnabled: false,
      passwordResetEnabled: false,
      googleEnabled: true,
    });
  });

  it("keeps password login on when the back-end fails, matching the back-end default", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("boom");
    });

    await expect(fetchAuthCapabilities(fetchImpl as unknown as typeof fetch)).resolves.toEqual({
      passwordEnabled: true,
      signupEnabled: false,
      passwordResetEnabled: false,
      googleEnabled: true,
    });
  });

  it("honours an explicit opt-out when the back-end is unreachable", async () => {
    vi.stubEnv("AUTH_PASSWORD_ENABLED", "false");
    const fetchImpl = vi.fn(async () => {
      throw new Error("boom");
    });

    await expect(fetchAuthCapabilities(fetchImpl as unknown as typeof fetch)).resolves.toEqual({
      passwordEnabled: false,
      signupEnabled: false,
      passwordResetEnabled: false,
      googleEnabled: true,
    });

    vi.unstubAllEnvs();
  });

  it("keeps sign-up on when the environment opts in and the back-end fails", async () => {
    vi.stubEnv("AUTH_PASSWORD_ENABLED", "true");
    const fetchImpl = vi.fn(async () => {
      throw new Error("boom");
    });

    await expect(fetchAuthCapabilities(fetchImpl as unknown as typeof fetch)).resolves.toEqual({
      passwordEnabled: true,
      signupEnabled: true,
      passwordResetEnabled: true,
      googleEnabled: true,
    });

    vi.unstubAllEnvs();
  });

  it("keeps sign-up off while sign-in stays on when the back-end fails without opt-in", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("boom");
    });

    await expect(fetchAuthCapabilities(fetchImpl as unknown as typeof fetch)).resolves.toEqual({
      passwordEnabled: true,
      signupEnabled: false,
      passwordResetEnabled: false,
      googleEnabled: true,
    });
  });

  it("falls back to the default contract when the payload is malformed", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ password_enabled: "yes" }));

    await expect(fetchAuthCapabilities(fetchImpl as unknown as typeof fetch)).resolves.toEqual({
      passwordEnabled: true,
      signupEnabled: false,
      passwordResetEnabled: false,
      googleEnabled: true,
    });
  });

  it("treats a failed response as a fallback, not as disabled", async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { status: 503 }));

    await expect(fetchAuthCapabilities(fetchImpl as unknown as typeof fetch)).resolves.toEqual({
      passwordEnabled: true,
      signupEnabled: false,
      passwordResetEnabled: false,
      googleEnabled: true,
    });
  });
});

describe("fetchPasswordPolicy", () => {
  it("normalizes the server policy", async () => {
    const fetchImpl = vi.fn(async () =>
      Response.json({
        min_length: 12,
        max_length: 96,
        requirements: ["min_length", 42],
        hibp_enabled: true,
      }),
    );

    await expect(fetchPasswordPolicy(fetchImpl as unknown as typeof fetch)).resolves.toEqual({
      minLength: 12,
      maxLength: 96,
      requirements: ["min_length"],
      hibpEnabled: true,
    });
  });

  it("falls back to the documented policy when the call fails", async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { status: 500 }));

    const policy = await fetchPasswordPolicy(fetchImpl as unknown as typeof fetch);

    expect(policy.minLength).toBe(10);
    expect(policy.maxLength).toBe(128);
    expect(policy.requirements).toContain("not_common");
  });
});
