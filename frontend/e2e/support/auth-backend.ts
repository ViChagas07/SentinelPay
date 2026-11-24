import type { Page, Route } from "@playwright/test";

export type AuthBackendOptions = {
  passwordEnabled?: boolean;
  signupEnabled?: boolean;
  login?: (body: { email?: string; senha?: string }) => {
    status: number;
    body: unknown;
    retryAfter?: string;
  };
  register?: (body: unknown) => { status: number; body: unknown };
  verify?: (body: { token?: string }) => { status: number; body: unknown };
  resend?: (body: unknown) => { status: number; body: unknown };
  forgot?: (body: unknown) => { status: number; body: unknown };
  reset?: (body: unknown) => { status: number; body: unknown };
};

type BackendHandler = (route: Route) => Promise<void> | void;

const POLICY = {
  min_length: 10,
  max_length: 128,
  requirements: ["min_length", "max_length", "not_common", "not_personal"],
  hibp_enabled: false,
};

function json(
  route: Route,
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): void {
  void route.fulfill({
    status,
    contentType: "application/json",
    headers,
    body: JSON.stringify(body),
  });
}

async function readBody(route: Route): Promise<Record<string, unknown>> {
  const request = route.request();
  const raw = request.postData();

  if (!raw) {
    return {};
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

export async function installAuthBackend(
  page: Page,
  options: AuthBackendOptions = {},
): Promise<void> {
  const enabled = options.passwordEnabled ?? true;
  const signupEnabled = options.signupEnabled ?? enabled;

  const handler: BackendHandler = async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204 });
      return;
    }

    if (path === "/api/v1/auth/capabilities") {
      json(route, 200, {
        password_enabled: enabled,
        signup_enabled: signupEnabled,
        password_reset_enabled: signupEnabled,
        google_enabled: true,
      });
      return;
    }

    if (path === "/api/v1/auth/password-policy") {
      json(route, 200, POLICY);
      return;
    }

    if (path === "/api/v1/auth/login" && request.method() === "POST") {
      const body = (await readBody(route)) as { email?: string; senha?: string };
      const result = options.login?.(body) ?? {
        status: 200,
        body: {
          access_token: "e2e-access",
          token_type: "bearer",
          expires_in: 900,
          user: { id: "user-1", email: body.email ?? "pessoa@example.com" },
        },
      };

      const headers: Record<string, string> = result.retryAfter
        ? { "retry-after": result.retryAfter }
        : {};

      if (result.status === 200) {
        const origin = new URL(page.url()).origin;
        const expiresAt = Date.now() + 900_000;

        await page.context().addCookies([
          { name: "sp_session", value: "e2e-access", url: origin, httpOnly: true, sameSite: "Lax" },
          {
            name: "sp_session_exp",
            value: String(expiresAt),
            url: origin,
            httpOnly: true,
            sameSite: "Lax",
          },
          {
            name: "sp_refresh",
            value: "e2e-refresh",
            url: origin,
            httpOnly: true,
            sameSite: "Lax",
          },
          { name: "sp_csrf", value: "e2e-csrf", url: origin, httpOnly: true, sameSite: "Lax" },
        ]);
      }

      json(route, result.status, result.body, headers);
      return;
    }

    if (path === "/api/v1/auth/register" && request.method() === "POST") {
      const body = await readBody(route);
      const result = options.register?.(body) ?? {
        status: 202,
        body: { status: "accepted" },
      };
      json(route, result.status, result.body);
      return;
    }

    if (path === "/api/v1/auth/verify-email" && request.method() === "POST") {
      const body = (await readBody(route)) as { token?: string };
      const result = options.verify?.(body) ?? { status: 204, body: null };

      if (result.status === 204) {
        await route.fulfill({ status: 204, body: "" });
        return;
      }

      json(route, result.status, result.body);
      return;
    }

    if (path === "/api/v1/auth/resend-verification" && request.method() === "POST") {
      const body = await readBody(route);
      const result = options.resend?.(body) ?? {
        status: 202,
        body: { status: "accepted" },
      };
      json(route, result.status, result.body);
      return;
    }

    if (path === "/api/v1/auth/forgot-password" && request.method() === "POST") {
      const body = await readBody(route);
      const result = options.forgot?.(body) ?? {
        status: 202,
        body: { status: "accepted" },
      };
      json(route, result.status, result.body);
      return;
    }

    if (path === "/api/v1/auth/reset-password" && request.method() === "POST") {
      const body = await readBody(route);
      const result = options.reset?.(body) ?? { status: 204, body: null };

      if (result.status === 204) {
        await route.fulfill({ status: 204, body: "" });
        return;
      }

      json(route, result.status, result.body);
      return;
    }

    json(route, 404, { code: "not_found" });
  };

  await page.route("**/api/v1/auth/**", handler);
}
