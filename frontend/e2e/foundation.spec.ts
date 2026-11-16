import { expect, test } from "@playwright/test";

test("switches theme and persists it in the cookie", async ({ page }) => {
  await page.goto("/");

  const header = page.getByRole("banner");
  const html = page.locator("html");
  await expect(html).toHaveAttribute("data-theme", "system");

  await header.getByRole("button", { name: /Tema/ }).click();
  await page.getByRole("menuitemradio", { name: "Escuro" }).click();
  await expect(html).toHaveAttribute("data-theme", "dark");

  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "dark");
});

test("switches language and persists it in the cookie", async ({ page }) => {
  await page.goto("/");

  const header = page.getByRole("banner");
  await header.getByRole("button", { name: /Idioma/ }).click();
  await page.getByRole("menuitemradio", { name: "Inglês" }).click();

  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Before you pay, check every signal.",
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "en");

  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Before you pay, check every signal.",
  );
});
