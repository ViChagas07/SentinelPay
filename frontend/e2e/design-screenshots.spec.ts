import { mkdir } from "node:fs/promises";

import { expect, test } from "@playwright/test";

test("captures design system screenshots in both themes", async ({ page, context }) => {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  await mkdir("docs/design", { recursive: true });
  await page.emulateMedia({ reducedMotion: "reduce" });

  for (const theme of ["light", "dark"] as const) {
    await context.addCookies([
      { name: "theme", value: theme, url: baseURL },
      { name: "locale", value: "pt", url: baseURL },
    ]);
    await page.goto("/dev/design");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: `docs/design/dev-design-${theme}.png`,
      fullPage: true,
    });
  }
});
