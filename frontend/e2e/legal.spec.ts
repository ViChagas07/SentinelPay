import { expect, test } from "@playwright/test";

test.describe("legal pages", () => {
  test("privacy table of contents navigates to a numbered section", async ({ page }) => {
    await page.goto("/privacidade");

    await expect(
      page.getByRole("heading", { level: 1, name: "Política de privacidade" }),
    ).toBeVisible();

    await page.locator('a[href="#dados-tratados"]:visible').first().click();

    await expect(page).toHaveURL(/\/privacidade#dados-tratados$/);
    await expect(
      page.getByRole("heading", { level: 2, name: "Quais dados tratamos" }),
    ).toBeVisible();
  });

  test("legal pages cross-link to each other", async ({ page }) => {
    await page.goto("/termos");
    await page.getByRole("link", { name: "Política de privacidade" }).first().click();
    await expect(page).toHaveURL(/\/privacidade$/);

    await page.getByRole("link", { name: "Termos de uso" }).first().click();
    await expect(page).toHaveURL(/\/termos$/);
  });

  test("login acceptance links open in a new tab and keep the form state", async ({
    page,
    context,
  }) => {
    await page.goto("/login");

    const checkbox = page.getByRole("checkbox");
    await checkbox.check();
    await expect(checkbox).toBeChecked();

    const popupPromise = context.waitForEvent("page");
    await page.getByRole("link", { name: "Termos de uso" }).click();
    const popup = await popupPromise;

    await expect(popup).toHaveURL(/\/termos$/);
    await expect(checkbox).toBeChecked();
  });
});
