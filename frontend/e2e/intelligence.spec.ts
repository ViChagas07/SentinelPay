import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { applyFakeSessionCookies, installFakeBackend } from "./support/fake-backend";

test.describe("intelligence", () => {
  test("shows an honest development state without invented metrics", async ({ page, context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    await applyFakeSessionCookies(context, baseURL);
    await installFakeBackend(page);
    await page.goto("/inteligencia");

    await expect(page.getByText("05", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 1, name: "Inteligência antifraude" }),
    ).toBeVisible();
    await expect(page.getByText("Em desenvolvimento")).toBeVisible();
    await expect(page.getByText("Esta visão ainda não tem dados.")).toBeVisible();
    await expect(
      page.getByText(
        "A API ainda não expõe catálogo de regras, casos históricos, métricas do classificador ou feedback. Esta visão será construída quando esses dados existirem.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Voltar ao painel" })).toHaveAttribute(
      "href",
      "/painel",
    );
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect(page.locator("table")).toHaveCount(0);

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    expect(results.violations).toEqual([]);
  });
});
