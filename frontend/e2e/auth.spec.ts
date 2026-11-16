import { expect, test } from "@playwright/test";

import {
  applySessionCookies,
  backendSessionAvailable,
  createBackendSession,
} from "./support/backend-session";

const available = backendSessionAvailable();
const skipReason = "API de testes indisponível: suba a stack com `docker compose up -d`.";

test.describe("session lifecycle against the real backend", () => {
  test.skip(!available, skipReason);

  test("anonymous user is sent to login with next", async ({ page }) => {
    await page.goto("/painel");
    await expect(page).toHaveURL(/\/login\?next=%2Fpainel/);
    await expect(page.getByRole("button", { name: /Continuar com Google/ })).toBeVisible();
  });

  test("login page keeps the original destination and clears unsafe next", async ({ page }) => {
    await page.goto("/login?next=%2Fboletos%3Fstatus%3Dpending");
    await expect(page.getByRole("button", { name: /Continuar com Google/ })).toBeVisible();

    await page.goto("/login?next=https%3A%2F%2Fevil.example");
    await expect(page.getByRole("button", { name: /Continuar com Google/ })).toBeVisible();
  });

  test("OIDC start goes to Google through the backend", async ({ page }) => {
    await page.goto("/login");

    const [request] = await Promise.all([
      page.waitForRequest((req) => req.url().includes("/api/v1/auth/login")),
      page.getByRole("button", { name: /Continuar com Google/ }).click(),
    ]);

    expect(request.url()).toContain("/api/v1/auth/login");

    await page.waitForURL(/accounts\.google\.com/, { timeout: 20_000 });
    expect(page.url()).toContain("accounts.google.com");
  });

  test("authenticated user loads the real profile and leaves login", async ({ page, context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    const session = createBackendSession();
    await applySessionCookies(context, session, baseURL);

    await page.goto("/login");
    await expect(page).toHaveURL(/\/painel$/);
    await expect(page.getByText(session.email).first()).toBeVisible();
  });

  test("logout invalidates the session and protects the area again", async ({ page, context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    const session = createBackendSession();
    await applySessionCookies(context, session, baseURL);
    await page.goto("/painel");
    await expect(page.getByText(session.email).first()).toBeVisible();

    await page
      .getByRole("button", { name: /Menu da conta/ })
      .first()
      .click();
    await page.getByRole("menuitem", { name: "Sair" }).click();
    await expect(page).toHaveURL(/\/login/);

    const cookies = await context.cookies(baseURL);
    expect(cookies.find((cookie) => cookie.name === "sp_session")).toBeUndefined();

    await page.goto("/painel");
    await expect(page).toHaveURL(/\/login\?next=%2Fpainel/);
  });

  test("expired access token is refreshed transparently by the BFF", async ({ page, context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    const session = createBackendSession();
    await context.addCookies([
      { name: "sp_session", value: "expired.token.value", url: baseURL, httpOnly: true },
      { name: "sp_refresh", value: session.refreshToken, url: baseURL, httpOnly: true },
      { name: "sp_csrf", value: session.csrfToken, url: baseURL, httpOnly: true },
      { name: "sp_session_exp", value: "1", url: baseURL, httpOnly: true },
    ]);

    await page.goto("/painel");
    await expect(page.getByText(session.email).first()).toBeVisible({ timeout: 20_000 });

    const cookies = await context.cookies(baseURL);
    const access = cookies.find((cookie) => cookie.name === "sp_session");
    expect(access?.value).not.toBe("expired.token.value");
    expect(access?.httpOnly).toBe(true);
  });

  test("revoked session redirects to login with the expired notice", async ({ page, context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    await context.addCookies([
      { name: "sp_session", value: "revoked.token.value", url: baseURL, httpOnly: true },
      { name: "sp_refresh", value: "revoked-refresh-token", url: baseURL, httpOnly: true },
      { name: "sp_csrf", value: "revoked-csrf", url: baseURL, httpOnly: true },
      { name: "sp_session_exp", value: "1", url: baseURL, httpOnly: true },
    ]);

    await page.goto("/painel");
    await expect(page).toHaveURL(/\/login\?.*reason=expired/, { timeout: 20_000 });
    await expect(page.getByText(/sua sessão expirou/i)).toBeVisible();
  });

  test("access token cookie is not readable from JavaScript", async ({ page, context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    const session = createBackendSession();
    await applySessionCookies(context, session, baseURL);
    await page.goto("/painel");

    const documentCookies = await page.evaluate(() => document.cookie);
    expect(documentCookies).not.toContain("sp_session");
    expect(documentCookies).not.toContain("sp_refresh");
    expect(documentCookies).not.toContain(session.accessToken);
    expect(documentCookies).not.toContain(session.refreshToken);

    const stored = await page.evaluate(() => ({
      local: Object.keys(window.localStorage),
      session: Object.keys(window.sessionStorage),
    }));
    expect(stored.local).toEqual([]);
    expect(stored.session).toEqual([]);
  });
});
