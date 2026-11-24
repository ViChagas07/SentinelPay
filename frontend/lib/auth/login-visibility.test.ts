import { describe, expect, it } from "vitest";

import { resolveLoginVisibility } from "@/lib/auth/login-visibility";

describe("resolveLoginVisibility", () => {
  it("shows both tabs when email sign-in and sign-up are enabled", () => {
    const result = resolveLoginVisibility({
      passwordEnabled: true,
      signupEnabled: true,
      policyAvailable: true,
      requestedMode: "signin",
    });

    expect(result.tabsVisible).toBe(true);
    expect(result.availableModes).toEqual(["signin", "signup"]);
    expect(result.emailSignupAvailable).toBe(true);
    expect(result.passwordFieldsVisible).toBe(true);
  });

  it("keeps both tabs visible when email sign-up is unavailable", () => {
    const result = resolveLoginVisibility({
      passwordEnabled: true,
      signupEnabled: false,
      policyAvailable: true,
      requestedMode: "signup",
    });

    expect(result.tabsVisible).toBe(true);
    expect(result.mode).toBe("signup");
    expect(result.emailSignupAvailable).toBe(false);
    expect(result.passwordFieldsVisible).toBe(true);
  });

  it("shows the sign-in fields on the sign-in tab without email sign-up", () => {
    const result = resolveLoginVisibility({
      passwordEnabled: true,
      signupEnabled: false,
      policyAvailable: true,
      requestedMode: "signin",
    });

    expect(result.passwordFieldsVisible).toBe(true);
  });

  it("hides the tabs and the fields when password login is disabled", () => {
    const result = resolveLoginVisibility({
      passwordEnabled: false,
      signupEnabled: true,
      policyAvailable: true,
      requestedMode: "signup",
    });

    expect(result.formsEnabled).toBe(false);
    expect(result.tabsVisible).toBe(false);
    expect(result.availableModes).toEqual(["signin"]);
    expect(result.mode).toBe("signin");
    expect(result.passwordFieldsVisible).toBe(false);
  });

  it("falls back to sign-in when the password policy is missing", () => {
    const result = resolveLoginVisibility({
      passwordEnabled: true,
      signupEnabled: true,
      policyAvailable: false,
      requestedMode: "signup",
    });

    expect(result.formsEnabled).toBe(false);
    expect(result.mode).toBe("signin");
    expect(result.passwordFieldsVisible).toBe(false);
  });
});
