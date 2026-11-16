import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const THEMES = ["light", "dark"] as const;

for (const theme of THEMES) {
  test(`login has no axe violations (${theme})`, async ({ page, context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    await context.addCookies([{ name: "theme", value: theme, url: baseURL }]);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/login");
    await expect(page.getByRole("button", { name: /Continuar com Google/ })).toBeVisible();

    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
}

test("login logo leads to the public home", async ({ page }) => {
  await page.goto("/login");
  await expect(page.locator("aside").getByRole("link", { name: "SentinelPay" })).toHaveAttribute(
    "href",
    "/",
  );
});

test("login error notice is announced", async ({ page }) => {
  await page.goto("/login?reason=auth_failed&code=email_not_verified");
  await expect(page.getByRole("heading", { level: 2 })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: /não está verificado/i })).toContainText(
    /não está verificado/i,
    {
      timeout: 10_000,
    },
  );
});

test("expired session notice is shown", async ({ page }) => {
  await page.goto("/login?reason=expired");
  await expect(page.getByRole("heading", { level: 2 })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: /expirou/i })).toContainText(/expirou/i, {
    timeout: 10_000,
  });
});

test("denied access notice is shown", async ({ page }) => {
  await page.goto("/login?reason=forbidden&code=forbidden");
  await expect(page.getByRole("heading", { level: 2 })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: /permissão/i })).toContainText(
    /permissão/i,
    {
      timeout: 10_000,
    },
  );
});
