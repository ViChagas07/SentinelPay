import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { middleware } from "@/middleware";

function makeRequest(path: string, cookies: Record<string, string> = {}): NextRequest {
  const header = Object.entries(cookies)
    .map(([name, value]) => `${name}=${value}`)
    .join("; ");
  const headers = new Headers();

  if (header) {
    headers.set("cookie", header);
  }

  return new NextRequest(`http://localhost:3000${path}`, { headers });
}

function locationOf(response: Response): string | null {
  const location = response.headers.get("location");
  return location ? new URL(location).pathname + new URL(location).search : null;
}

describe("middleware", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("redirects anonymous users from private routes to login with next", () => {
    const response = middleware(makeRequest("/boletos?status=pending"));

    expect(response.status).toBe(307);
    expect(locationOf(response)).toBe("/login?next=%2Fboletos%3Fstatus%3Dpending");
  });

  it("allows anonymous users on public routes", () => {
    for (const path of ["/", "/login", "/termos", "/privacidade"]) {
      const response = middleware(makeRequest(path));
      expect(response.headers.get("location")).toBeNull();
    }
  });

  it("redirects authenticated users from login to painel", () => {
    const response = middleware(makeRequest("/login", { sp_session: "token" }));
    expect(locationOf(response)).toBe("/painel");
  });

  it("honors a safe next destination for authenticated users on login", () => {
    const response = middleware(
      makeRequest("/login?next=%2Fnotificacoes", { sp_session: "token" }),
    );
    expect(locationOf(response)).toBe("/notificacoes");
  });

  it("allows authenticated users on private routes", () => {
    const response = middleware(makeRequest("/painel", { sp_session: "token" }));
    expect(response.headers.get("location")).toBeNull();
  });

  it("routes back from the OIDC callback using the pending next cookie", () => {
    const response = middleware(makeRequest("/?code=abc&state=xyz", { sp_oidc: "/folha" }));

    expect(response.status).toBe(307);
    expect(locationOf(response)).toBe("/api/v1/auth/complete");
  });

  it("does not intercept the complete endpoint itself", () => {
    const response = middleware(makeRequest("/api/v1/auth/complete", { sp_oidc: "/folha" }));
    expect(response.headers.get("location")).toBeNull();
  });

  it("allows unknown routes without a session", () => {
    const response = middleware(makeRequest("/qualquer-coisa"));
    expect(response.headers.get("location")).toBeNull();
  });

  it("blocks the design catalogue outside development", () => {
    vi.stubEnv("NODE_ENV", "production");
    const response = middleware(makeRequest("/dev/design"));
    expect(response.status).toBe(404);
  });
});
