import { expect, test } from "@playwright/test";

test("security headers are present on every route", async ({ request }) => {
  const response = await request.get("/");
  expect(response.ok()).toBe(true);

  const headers = response.headers();
  const csp = headers["content-security-policy"] ?? "";

  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("object-src 'none'");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).toContain("base-uri 'self'");
  expect(csp).toContain("form-action 'self'");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["permissions-policy"]).toContain("camera=()");
  expect(headers["cross-origin-opener-policy"]).toBe("same-origin");
  expect(headers["x-powered-by"]).toBeUndefined();
});

test("the BFF clear-session cookies are HttpOnly and SameSite=Lax", async ({ request }) => {
  const response = await request.post("/api/v1/auth/logout");
  expect(response.status()).toBe(204);

  const setCookies = response
    .headersArray()
    .filter((header) => header.name.toLowerCase() === "set-cookie")
    .map((header) => header.value);

  expect(setCookies.length).toBeGreaterThan(0);

  for (const cookie of setCookies) {
    expect(cookie.toLowerCase()).toContain("httponly");
    expect(cookie.toLowerCase()).toContain("samesite=lax");
    expect(cookie.toLowerCase()).toContain("max-age=0");
  }
});

test("session tokens are never exposed through document.cookie", async ({ page, context }) => {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  await context.addCookies([
    { name: "sp_session", value: "token-de-teste", url: baseURL, httpOnly: true },
    { name: "sp_refresh", value: "refresh-de-teste", url: baseURL, httpOnly: true },
    { name: "sp_csrf", value: "csrf-de-teste", url: baseURL, httpOnly: true },
  ]);
  await page.goto("/login");
  await page.evaluate(() => document.fonts.ready);

  const cookie = await page.evaluate(() => document.cookie);
  expect(cookie).not.toContain("sp_session");
  expect(cookie).not.toContain("sp_refresh");
  expect(cookie).not.toContain("sp_csrf");
  expect(cookie).not.toContain("token-de-teste");
});
