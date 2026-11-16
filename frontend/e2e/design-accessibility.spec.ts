import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const THEMES = ["light", "dark"] as const;
const LOCALES = ["pt", "es", "en"] as const;

for (const theme of THEMES) {
  for (const locale of LOCALES) {
    test(`design system has no axe violations (${theme}, ${locale})`, async ({ page, context }) => {
      const baseURL = test.info().project.use.baseURL;

      if (!baseURL) {
        throw new Error("Playwright baseURL is not configured");
      }

      await context.addCookies([
        { name: "theme", value: theme, url: baseURL },
        { name: "locale", value: locale, url: baseURL },
      ]);
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.goto("/dev/design");
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations).toEqual([]);
    });
  }
}
