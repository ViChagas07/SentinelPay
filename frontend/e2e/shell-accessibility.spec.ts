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

let session: BackendSession | undefined;

test.beforeAll(() => {
  if (!available) {
    return;
  }

  session = createBackendSession();
});

for (const theme of ["light", "dark"] as const) {
  test(`shell has no axe violations (${theme})`, async ({ page, context }) => {
    test.skip(!available, skipReason);

    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    if (!session) {
      throw new Error("Backend session missing.");
    }

    await applySessionCookies(context, session, baseURL);
    await context.addCookies([{ name: "theme", value: theme, url: baseURL }]);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/painel");
    await expect(page.locator('aside nav[aria-label="Navegação principal"]')).toBeVisible({
      timeout: 20_000,
    });

    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
}
