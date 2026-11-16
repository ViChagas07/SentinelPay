import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

function wcagAudit(page: Page) {
  return new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
}

async function openShowcase(page: Page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/dev/design");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
}

test.describe("design system overlays", () => {
  test.beforeEach(async ({ context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    await context.addCookies([
      { name: "theme", value: "light", url: baseURL },
      { name: "locale", value: "pt", url: baseURL },
    ]);
  });

  test("toast has no axe violations", async ({ page }) => {
    await openShowcase(page);
    await page.getByRole("button", { name: "Mostrar toast" }).click();
    await expect(page.getByText("Alterações salvas.").first()).toBeVisible();

    const results = await wcagAudit(page);
    expect(results.violations).toEqual([]);
  });

  test("dialog has no axe violations", async ({ page }) => {
    await openShowcase(page);
    await page.getByRole("button", { name: "Abrir diálogo" }).click();
    await expect(page.getByRole("dialog", { name: "Confirmação" })).toBeVisible();

    const results = await wcagAudit(page);
    expect(results.violations).toEqual([]);
  });

  test("sheet has no axe violations", async ({ page }) => {
    await openShowcase(page);
    await page.getByRole("button", { name: "Abrir painel" }).click();
    await expect(page.getByRole("dialog", { name: "Painel lateral" })).toBeVisible();

    const results = await wcagAudit(page);
    expect(results.violations).toEqual([]);
  });

  test("command palette has no axe violations", async ({ page }) => {
    await openShowcase(page);
    await page.getByRole("button", { name: "Abrir paleta" }).click();
    await expect(page.getByRole("dialog", { name: "Paleta de comandos" })).toBeVisible();

    const results = await wcagAudit(page);
    expect(results.violations).toEqual([]);
  });

  test("select has no axe violations", async ({ page }) => {
    await openShowcase(page);
    await page.getByRole("combobox", { name: /Opção/ }).click();
    await expect(page.getByRole("listbox")).toBeVisible();

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .exclude(".min-h-dvh.flex-col")
      .exclude(".skip-link")
      .analyze();
    expect(results.violations).toEqual([]);
  });

  test("tooltip has no axe violations", async ({ page }) => {
    await openShowcase(page);
    await page.getByRole("button", { name: "Ajuda" }).focus();
    await expect(page.getByRole("tooltip")).toBeVisible();

    const results = await wcagAudit(page);
    expect(results.violations).toEqual([]);
  });
});
