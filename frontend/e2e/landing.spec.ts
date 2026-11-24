import { expect, test } from "@playwright/test";

test("landing shows the editorial sections and the illustrative label", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Antes de pagar, confira cada sinal.",
  );

  const nav = page.getByRole("banner").getByRole("navigation", { name: "Navegação da página" });
  await expect(nav.getByRole("link", { name: "Como funciona", exact: true })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Recursos", exact: true })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Normas", exact: true })).toBeVisible();

  await expect(page.locator("figcaption")).toHaveText("Exemplo ilustrativo");
  await expect(page.getByRole("heading", { level: 2, name: /Uma decisão melhor/ })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /Um índice\./ })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /Fontes registradas/ })).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 2, name: "Clareza antes de confirmar." }),
  ).toBeVisible();

  await expect(page.getByRole("link", { name: /Painel Principal/ })).toHaveAttribute(
    "href",
    "/painel",
  );
  await expect(page.getByRole("link", { name: /Central de Verificação/ })).toHaveAttribute(
    "href",
    "/verificacao",
  );
  await expect(page.getByRole("link", { name: /Boleto Bancário/ })).toHaveAttribute(
    "href",
    "/boletos",
  );
  await expect(page.getByRole("link", { name: /Folha de Pagamento/ })).toHaveAttribute(
    "href",
    "/folha",
  );
  await expect(page.getByRole("link", { name: /Notificações/ })).toHaveAttribute(
    "href",
    "/notificacoes",
  );
  await expect(page.getByRole("link", { name: /Inteligência Antifraude/ })).toHaveAttribute(
    "href",
    "/inteligencia",
  );
  await expect(page.getByRole("link", { name: /Central de Pagamentos/ })).toHaveAttribute(
    "href",
    "/pagamentos",
  );
});

test("header CTA targets the dashboard and the middleware protects it", async ({ page }) => {
  await page.goto("/");

  const cta = page.getByRole("banner").getByRole("link", { name: "Entrar no painel" });
  await expect(cta).toHaveAttribute("href", "/painel");

  await cta.click();
  await expect(page).toHaveURL(/\/login\?next=%2Fpainel/, { timeout: 20_000 });
});

test("header label changes when a session cookie exists", async ({ page, context }) => {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  await context.addCookies([{ name: "sp_session", value: "test-session", url: baseURL }]);
  await page.goto("/");

  await expect(
    page.getByRole("banner").getByRole("link", { name: "Ir para o painel" }),
  ).toBeVisible();
});

test("landing renders Spanish and English from the locale cookie", async ({ page, context }) => {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  await context.addCookies([{ name: "locale", value: "es", url: baseURL }]);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Antes de pagar, revisa cada señal.",
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "es");

  await context.addCookies([{ name: "locale", value: "en", url: baseURL }]);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Before you pay, check every signal.",
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test("risk index responds to the keyboard and keeps the caveat", async ({ page }) => {
  await page.goto("/");

  const riskSection = page.locator("#indice-risco");
  const slider = page.getByRole("slider", { name: "Índice de risco de 0 a 100" });

  await slider.focus();
  await page.keyboard.press("Home");
  await expect(riskSection.getByText("Baixo", { exact: true })).toBeVisible();
  await expect(riskSection.getByText(/Poucos sinais objetivos/)).toBeVisible();

  await page.keyboard.press("End");
  await expect(riskSection.getByText("Alto", { exact: true })).toBeVisible();
  await expect(riskSection.getByText(/Há sinais relevantes ou críticos/)).toBeVisible();

  await page.keyboard.press("ArrowLeft");
  await expect(riskSection.getByText("Alto", { exact: true })).toBeVisible();

  await expect(riskSection.getByText(/O índice organiza sinais para revisão/)).toBeVisible();
});

test("risk index class badge follows the band and the ruler spans the card", async ({ page }) => {
  await page.goto("/");

  const riskSection = page.locator("#indice-risco");
  const slider = page.getByRole("slider", { name: "Índice de risco de 0 a 100" });
  const badge = riskSection.getByText("Baixo", { exact: true });

  await slider.focus();
  await page.keyboard.press("Home");
  await expect(badge).toBeVisible();
  await expect(badge).toHaveCSS("background-color", "rgb(46, 107, 80)");

  await page.keyboard.press("End");
  await expect(riskSection.getByText("Alto", { exact: true })).toHaveCSS(
    "background-color",
    "rgb(200, 64, 47)",
  );

  const geometry = await page.evaluate(() => {
    const section = document.getElementById("indice-risco");
    const input = section?.querySelector<HTMLInputElement>("input[type=range]");
    const card = input?.closest(".rounded-\\[6px\\]");

    if (!section || !input || !card) {
      return null;
    }

    const inputRect = input.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    const style = getComputedStyle(card);

    return {
      available: cardRect.width - Number.parseFloat(style.paddingLeft) * 2,
      inputWidth: inputRect.width,
    };
  });

  expect(geometry).not.toBeNull();
  expect(geometry!.inputWidth).toBeGreaterThanOrEqual(geometry!.available - 2);
});

test("landing has no horizontal scroll on narrow screens", async ({ page, context }) => {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  await context.addCookies([
    { name: "theme", value: "light", url: baseURL },
    { name: "locale", value: "pt", url: baseURL },
  ]);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");

  const hasHorizontalScroll = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(hasHorizontalScroll).toBe(false);
});

test("landing exposes SEO metadata and a next/og image", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle(/SentinelPay/);
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    "content",
    /Confira boletos/,
  );
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", /SentinelPay/);
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
    "content",
    /opengraph-image/,
  );

  const response = await page.request.get("/opengraph-image");
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("image/png");
});
