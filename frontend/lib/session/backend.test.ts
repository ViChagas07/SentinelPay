import { afterEach, describe, expect, it, vi } from "vitest";

import type { CookieReader } from "./cookies";
import { buildForwardCookies, readSetCookies, requestRefresh, toLoginErrorCode } from "./backend";
import { buildClearSessionCookies, buildSessionCookies, expiredResponse } from "./server";

function reader(values: Record<string, string | undefined>): CookieReader {
  return {
    get(name: string) {
      const value = values[name];
      return value === undefined ? undefined : { value };
    },
  };
}

function refreshResponse(): Response {
  const headers = new Headers({ "content-type": "application/json" });
  headers.append("set-cookie", "refresh_token=new; Path=/api/v1/auth; HttpOnly");
  headers.append("set-cookie", "csrf_token=newcsr; Path=/");

  return new Response(
    JSON.stringify({
      access_token: "header.payload.signature",
      token_type: "bearer",
      expires_in: 900,
      user: { id: "u1" },
    }),
    { status: 200, headers },
  );
}

describe("requestRefresh", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns missing when there is no refresh or csrf cookie", async () => {
    await expect(
      requestRefresh({
        cookies: reader({ refresh_token: "r" }),
        backendUrl: "http://api/api/v1/auth/refresh",
      }),
    ).resolves.toEqual({ kind: "missing" });
  });

  it("sends refresh, csrf cookie and header, then keeps rotated cookies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(refreshResponse());
    vi.stubGlobal("fetch", fetchMock);

    const outcome = await requestRefresh({
      cookies: reader({ refresh_token: "old", csrf_token: "oldcsr" }),
      backendUrl: "http://api/api/v1/auth/refresh",
    });

    const [, init] = fetchMock.mock.calls[0] ?? [];
    const headers = new Headers(init?.headers);
    expect(headers.get("X-CSRF-Token")).toBe("oldcsr");
    expect(headers.get("Cookie")).toBe("refresh_token=old; csrf_token=oldcsr");
    expect(init).toMatchObject({ method: "POST", cache: "no-store" });

    expect(outcome.kind).toBe("refreshed");

    if (outcome.kind === "refreshed") {
      expect(outcome.session.accessToken).toBe("header.payload.signature");
      expect(outcome.session.expiresInSeconds).toBe(900);
      expect(outcome.setCookies).toHaveLength(2);
    }
  });

  it("reports a failed refresh with the backend code and clearing cookies", async () => {
    const headers = new Headers({ "content-type": "application/problem+json" });
    headers.append("set-cookie", "refresh_token=; Path=/api/v1/auth; Max-Age=0");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ code: "invalid_refresh_token" }), {
        status: 401,
        headers,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const outcome = await requestRefresh({
      cookies: reader({ refresh_token: "old", csrf_token: "oldcsr" }),
      backendUrl: "http://api/api/v1/auth/refresh",
    });

    expect(outcome).toMatchObject({
      kind: "failed",
      code: "invalid_refresh_token",
      status: 401,
    });

    if (outcome.kind === "failed") {
      expect(outcome.setCookies).toHaveLength(1);
    }
  });

  it("maps network failures to a 502 with a login-safe code", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);

    const outcome = await requestRefresh({
      cookies: reader({ refresh_token: "old", csrf_token: "oldcsr" }),
      backendUrl: "http://api/api/v1/auth/refresh",
    });

    expect(outcome).toMatchObject({ kind: "failed", code: "network_error", status: 502 });
    expect(toLoginErrorCode("network_error")).toBe("network_error");
    expect(toLoginErrorCode("invalid_refresh_token")).toBeNull();
  });
});

describe("session cookies", () => {
  it("builds a session cookie without exposing the token to JS", () => {
    const cookies = buildSessionCookies("abc.def.ghi", 900, false);

    expect(cookies.session).toContain("sp_session=abc.def.ghi");
    expect(cookies.session).toContain("HttpOnly");
    expect(cookies.session).toContain("SameSite=Lax");
    expect(cookies.session).toContain("Path=/");
    expect(cookies.session).toContain("Max-Age=604800");
    expect(cookies.session).not.toContain("Secure");
    expect(cookies.expiry).toMatch(/^sp_session_exp=\d+;/);
  });

  it("marks cookies as Secure on https requests", () => {
    expect(buildSessionCookies("abc", 900, true).session).toContain("Secure");
    expect(buildClearSessionCookies(true).every((cookie) => cookie.includes("Secure"))).toBe(true);
  });

  it("clears both session cookies", () => {
    const cleared = buildClearSessionCookies(false);
    expect(cleared).toHaveLength(4);
    expect(cleared[0]).toContain("sp_session=;");
    expect(cleared[1]).toContain("sp_session_exp=;");
    expect(cleared[2]).toContain("sp_refresh=;");
    expect(cleared[3]).toContain("sp_csrf=;");
    expect(cleared.every((cookie) => cookie.includes("Max-Age=0"))).toBe(true);
  });

  it("builds a problem response with the expired code", async () => {
    const response = expiredResponse();
    expect(response.status).toBe(401);
    expect(response.headers.get("content-type")).toBe("application/problem+json");
    await expect(response.json()).resolves.toMatchObject({ code: "session_expired" });
  });

  it("forwards only refresh and csrf cookies to the backend", () => {
    expect(
      buildForwardCookies(
        reader({
          refresh_token: "r",
          csrf_token: "c",
          sp_session: "should-not-leak",
          sp_oidc: "/painel",
        }),
      ),
    ).toBe("refresh_token=r; csrf_token=c");
  });

  it("reads multiple set-cookie headers", () => {
    const headers = new Headers();
    headers.append("set-cookie", "a=1");
    headers.append("set-cookie", "b=2");
    expect(readSetCookies(headers)).toEqual(["a=1", "b=2"]);
  });
});
