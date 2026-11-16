import { describe, expect, it } from "vitest";

import { hasSessionCookie, isSecureRequest, readOidcNext } from "./cookies";

function reader(values: Record<string, string | undefined>) {
  return {
    get(name: string) {
      const value = values[name];
      return value === undefined ? undefined : { value };
    },
  };
}

describe("session cookies", () => {
  it("detects a non-empty session cookie", () => {
    expect(hasSessionCookie(reader({ sp_session: "token" }))).toBe(true);
    expect(hasSessionCookie(reader({ sp_session: "" }))).toBe(false);
    expect(hasSessionCookie(reader({}))).toBe(false);
  });

  it("reads the pending next destination only when present", () => {
    expect(readOidcNext(reader({ sp_oidc: "/boletos" }))).toBe("/boletos");
    expect(readOidcNext(reader({ sp_oidc: "" }))).toBeUndefined();
    expect(readOidcNext(reader({}))).toBeUndefined();
  });

  it("trusts the forwarded https protocol on secure cookie flags", () => {
    expect(isSecureRequest("http://app.test", "https")).toBe(true);
    expect(isSecureRequest("http://app.test", "https, http")).toBe(true);
    expect(isSecureRequest("https://app.test", null)).toBe(true);
    expect(isSecureRequest("http://app.test", "http")).toBe(false);
    expect(isSecureRequest("http://localhost:3000")).toBe(false);
  });
});
