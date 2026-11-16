import { expect, test } from "@playwright/test";

test("data table stacks on mobile without horizontal scrolling", async ({ page, context }) => {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  await context.addCookies([
    { name: "theme", value: "light", url: baseURL },
    { name: "locale", value: "pt", url: baseURL },
  ]);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dev/design");
  await page.locator("#data").scrollIntoViewIfNeeded();

  await expect(page.getByRole("table", { name: "Tabela de demonstração" })).toBeHidden();
  await expect(page.getByRole("list", { name: "Tabela de demonstração" })).toBeVisible();

  const hasHorizontalScroll = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(hasHorizontalScroll).toBe(false);
});
