import { expect, test } from "@playwright/test";

import { applyFakeSessionCookies, installFakeBackend, problem } from "./support/fake-backend";
test("429 shows a friendly notice and respects Retry-After", async ({ page, context }) => {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  await applyFakeSessionCookies(context, baseURL);
  await installFakeBackend(page, {
    list: {
      status: 429,
      contentType: "application/problem+json",
      headers: { "retry-after": "5" },
      body: {
        type: "https://paysentineliq.local/problems/rate_limited",
        title: "Too many requests",
        status: 429,
        detail: "Too many requests.",
        instance: "/api/v1/analyses",
        code: "rate_limited",
        request_id: "req-e2e",
      },
    },
  });

  await page.goto("/boletos");
  await expect(page.getByText("Muitas solicitações")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Aguarde 5 s e tente novamente.")).toBeVisible();
});

test("401 sends the user back to login with the current destination", async ({ page, context }) => {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  await applyFakeSessionCookies(context, baseURL);
  await installFakeBackend(page, {
    list: { status: 200, body: { items: [], next_cursor: null } },
  });
  await page.route(/\/api\/v1\/analyses(\?|$)/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800));
    await context.clearCookies({ name: "sp_session" });
    await route.fulfill({
      status: 401,
      contentType: "application/problem+json",
      headers: { "x-request-id": "req-e2e" },
      body: JSON.stringify(problem(401, "session_expired", "Session expired.").body),
    });
  });

  await page.goto("/boletos");
  await expect(page).toHaveURL(/\/login\?/, { timeout: 20_000 });
  await expect(page.locator("main")).toBeVisible({ timeout: 20_000 });
});
