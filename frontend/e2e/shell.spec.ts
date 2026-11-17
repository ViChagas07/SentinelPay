import { expect, test } from "@playwright/test";

import {
  applySessionCookies,
  backendSessionAvailable,
  createBackendSession,
  type BackendSession,
} from "./support/backend-session";

const available = backendSessionAvailable();
const skipReason = "API de testes indisponível: suba a stack com `docker compose up -d`.";

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

const NAV_HREFS = [
  "/painel",
  "/pagamentos",
  "/verificacao",
  "/inteligencia",
  "/folha",
  "/boletos",
  "/notificacoes",
];

test.describe("authenticated shell", () => {
  let session: BackendSession | undefined;

  test.beforeAll(() => {
    if (!available) {
      return;
    }

    session = createBackendSession();
  });

  test.beforeEach(async ({ context }) => {
    test.skip(!available, skipReason);

    if (!session) {
      throw new Error("Backend session missing.");
    }

    await applySessionCookies(context, session, requireBaseUrl());
  });

  test("keeps the requested navigation order and navigates", async ({ page }) => {
    await page.goto("/painel");

    const sidebar = page.locator("aside");
    const links = sidebar.locator('nav[aria-label="Navegação principal"] a');

    await expect(links).toHaveCount(NAV_HREFS.length, { timeout: 20_000 });
    expect(
      await links.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href"))),
    ).toEqual(NAV_HREFS);

    await sidebar.getByRole("link", { name: "Central de Verificação" }).click();
    await expect(page).toHaveURL(/\/verificacao$/);
    await expect(page.getByRole("banner").getByText("Central de Verificação")).toBeVisible();

    await sidebar.getByRole("link", { name: "Boleto Bancário" }).click();
    await expect(page).toHaveURL(/\/boletos$/);
    await expect(sidebar.getByRole("link", { name: "Boleto Bancário" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("logo always lands on the dashboard", async ({ page }) => {
    await page.goto("/painel");

    const logo = page.locator('aside a[aria-label="SentinelPay"]');
    await expect(logo).toHaveAttribute("href", "/painel", { timeout: 20_000 });
    await logo.click();
    await expect(page).toHaveURL(/\/painel$/);
  });

  test("collapses to rail, shows tooltips and persists the choice", async ({ page }) => {
    await page.goto("/painel");

    const aside = page.locator("aside");
    await expect(aside).toHaveAttribute("data-collapsed", "false", { timeout: 20_000 });

    await page.getByRole("button", { name: "Recolher menu" }).click();
    await expect(aside).toHaveAttribute("data-collapsed", "true");

    await aside.getByRole("link", { name: "Painel Principal" }).hover();
    await expect(page.getByRole("tooltip")).toContainText("Painel Principal");

    await page.reload();
    await expect(aside).toHaveAttribute("data-collapsed", "true", { timeout: 20_000 });

    await page.getByRole("button", { name: "Expandir menu" }).click();
    await expect(aside).toHaveAttribute("data-collapsed", "false");
  });

  test("does not show a drawer close button on desktop", async ({ page }) => {
    await page.goto("/painel");
    await expect(page.getByRole("banner")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("button", { name: "Fechar" })).toHaveCount(0);
  });

  test("mobile sheet has a single close button and closes on navigation", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto("/painel");
    await expect(page.getByRole("banner")).toBeVisible({ timeout: 20_000 });

    await page.getByRole("button", { name: "Abrir menu" }).click();

    const sheet = page.getByRole("dialog", { name: "Navegação principal" });
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("button", { name: "Fechar" })).toHaveCount(1);

    await sheet.getByRole("button", { name: /e2e\.session@/ }).click();
    await expect(page.getByRole("menuitem", { name: "Minha conta" })).toBeVisible();
    await page.keyboard.press("Escape");

    await sheet.getByRole("link", { name: "Central de Pagamentos" }).click();
    await expect(page).toHaveURL(/\/pagamentos$/);
    await expect(sheet).toBeHidden();

    const hasHorizontalScroll = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(hasHorizontalScroll).toBe(false);
  });

  test("command palette searches honestly and navigates", async ({ page }) => {
    await page.goto("/painel");
    await expect(page.locator('aside nav[aria-label="Navegação principal"]')).toBeVisible({
      timeout: 20_000,
    });
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(300);
    await page.keyboard.press("Control+k");

    const palette = page.getByRole("dialog", { name: "Busca e comandos" });
    await expect(palette).toBeVisible();
    await expect(palette.getByText("Busca de documentos indisponível")).toBeVisible();

    await palette.getByRole("option", { name: /Central de Verificação/ }).click();
    await expect(page).toHaveURL(/\/verificacao$/);
  });

  test("keyboard shortcuts navigate and open the shortcut list", async ({ page }) => {
    await page.goto("/notificacoes");
    await expect(page.locator('aside nav[aria-label="Navegação principal"]')).toBeVisible();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(300);

    await page.keyboard.press("g");
    await page.keyboard.press("p");
    await expect(page).toHaveURL(/\/painel$/);

    await page.keyboard.press("g");
    await page.keyboard.press("v");
    await expect(page).toHaveURL(/\/verificacao$/);

    await page.keyboard.press("n");
    await expect(page).toHaveURL(/\/verificacao\/nova$/);

    await page.keyboard.press("?");
    const shortcuts = page.getByRole("dialog", { name: "Atalhos de teclado" });
    await expect(shortcuts).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(shortcuts).toBeHidden();
  });

  test("user menu reaches the account page and signs out", async ({ page, context }) => {
    await applySessionCookies(context, createBackendSession(), requireBaseUrl());
    await page.goto("/painel");
    await expect(page.getByRole("banner")).toBeVisible({ timeout: 20_000 });

    await page
      .getByRole("button", { name: /Menu da conta/ })
      .first()
      .click();
    await page.getByRole("menuitem", { name: "Minha conta" }).click();
    await expect(page).toHaveURL(/\/account$/, { timeout: 20_000 });
    await expect(page.locator("header").getByText("Minha conta").first()).toBeVisible();

    const breadcrumbs = page.getByRole("navigation", { name: "Trilha de navegação" });
    await expect(breadcrumbs.getByText("Painel Principal")).toBeVisible();
    await expect(breadcrumbs.getByText("Minha conta")).toBeVisible();

    await page
      .getByRole("button", { name: /Menu da conta/ })
      .first()
      .click();
    await page.getByRole("menuitem", { name: "Sair" }).click();
    await expect(page).toHaveURL(/\/login/);

    await page.goto("/painel");
    await expect(page).toHaveURL(/\/login\?next=%2Fpainel/);
  });

  test("has no horizontal scroll from 360 to 1920", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await page.goto("/painel");
    await expect(page.getByRole("banner")).toBeVisible({ timeout: 20_000 });

    for (const width of [360, 768, 1024, 1440, 1920]) {
      await test.step(`width ${width}`, async () => {
        await page.setViewportSize({ width, height: 900 });

        const hasHorizontalScroll = await page.evaluate(
          () => document.documentElement.scrollWidth > window.innerWidth,
        );
        expect(hasHorizontalScroll).toBe(false);
      });
    }
  });

  test("help card uses the support url from the environment", async ({ page }) => {
    await page.goto("/painel");
    await expect(page.getByRole("link", { name: /Precisa de ajuda/ })).toHaveAttribute(
      "href",
      "https://support.sentinelpay.test/",
      { timeout: 20_000 },
    );
  });

  test("header language selector updates the shell labels", async ({ page }) => {
    await page.goto("/painel");
    await expect(page.getByRole("banner")).toBeVisible({ timeout: 20_000 });

    await page.getByRole("button", { name: "Idioma: Português PT" }).click();
    await page.getByRole("menuitemradio", { name: "Inglês" }).click();

    await expect(page.locator("header").getByText("Main dashboard").first()).toBeVisible();
    await expect(page.locator("aside").getByRole("link", { name: "Main dashboard" })).toBeVisible();
  });
});
