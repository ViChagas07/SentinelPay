import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import {
  applySessionCookies,
  backendSessionAvailable,
  createBackendSession,
  type BackendSession,
} from "./support/backend-session";

const available = backendSessionAvailable();
const skipReason = "API de testes indisponível: suba a stack com `docker compose up -d`.";

const CASES = [
  { theme: "light", locale: "pt" },
  { theme: "dark", locale: "en" },
] as const;

test.describe("dashboard accessibility", () => {
  let session: BackendSession | undefined;

  test.beforeAll(() => {
    if (!available) {
      return;
    }

    session = createBackendSession({ seedDashboard: true });
  });

  test.beforeEach(() => {
    test.skip(!available, skipReason);
  });

  for (const testCase of CASES) {
    test(`has no axe violations (${testCase.theme}, ${testCase.locale})`, async ({
      page,
      context,
    }) => {
      const baseURL = test.info().project.use.baseURL;

      if (!baseURL) {
        throw new Error("Playwright baseURL is not configured");
      }

      if (!session) {
        throw new Error("Seeded session missing.");
      }

      await applySessionCookies(context, session, baseURL);
      await context.addCookies([
        { name: "theme", value: testCase.theme, url: baseURL },
        { name: "locale", value: testCase.locale, url: baseURL },
      ]);
      await page.emulateMedia({
        reducedMotion: "reduce",
        colorScheme: testCase.theme === "dark" ? "dark" : "light",
      });
      await page.goto("/painel");

      await expect(page.locator("section[aria-labelledby='dashboard-risk-title']")).toBeVisible({
        timeout: 20_000,
      });
      await expect(
        page.locator("section[aria-labelledby='dashboard-recent-title'] table"),
      ).toBeVisible({ timeout: 20_000 });
      await expect(
        page.locator("section[aria-labelledby='dashboard-distribution-title']"),
      ).toBeVisible({ timeout: 20_000 });
      await expect(page.getByRole("progressbar").first()).toBeVisible({
        timeout: 20_000,
      });

      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations).toEqual([]);
    });
  }
});
