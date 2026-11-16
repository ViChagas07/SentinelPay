import { expect, test } from "@playwright/test";

import {
  applySessionCookies,
  backendSessionAvailable,
  createBackendSession,
  type BackendSession,
  type DashboardSeed,
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

test.describe("dashboard with seeded backend data", () => {
  let session: BackendSession | undefined;
  let seed: DashboardSeed | undefined;

  test.beforeAll(() => {
    if (!available) {
      return;
    }

    const created = createBackendSession({ seedDashboard: true });

    if (!created.seed) {
      throw new Error("Dashboard seed missing from the session script.");
    }

    session = created;
    seed = created.seed;
  });

  test.beforeEach(async ({ context }) => {
    test.skip(!available, skipReason);

    if (!session) {
      throw new Error("Seeded session missing.");
    }

    await applySessionCookies(context, session, requireBaseUrl());
  });

  function requireSeed(): DashboardSeed {
    if (!seed) {
      throw new Error("Dashboard seed missing.");
    }

    return seed;
  }

  test("greets with the real user name and the current local date", async ({ page }) => {
    await page.goto("/painel");

    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Olá, Sessão de teste", {
      timeout: 20_000,
    });

    const expectedDate = new Intl.DateTimeFormat("pt-BR", {
      weekday: "long",
      day: "2-digit",
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }).format(new Date());

    await expect(page.getByText(expectedDate)).toBeVisible();
  });

  test("shows average risk and keeps compliance out of the ruler", async ({ page }) => {
    const data = requireSeed();

    await page.goto("/painel");

    const risk = page.getByRole("region", { name: "Risco médio" });
    await expect(risk).toBeVisible({ timeout: 20_000 });
    const meter = risk.getByRole("meter");

    await expect(meter).toHaveAttribute("aria-valuenow", String(data.average));
    await expect(risk.getByText(String(data.average), { exact: true }).first()).toBeVisible();
    await expect(risk.getByText(/pts vs\. 30 dias anteriores/)).toBeVisible();
    await expect(
      risk.getByText(/2 de 4 análises concluídas ficaram em atenção ou alto/),
    ).toBeVisible();
    await expect(risk.getByText(/Faixa calculada sobre a média/)).toBeVisible();

    const conformity = page.getByRole("progressbar", {
      name: "Documentos em conformidade",
    });

    await expect(conformity).toHaveAttribute("aria-valuenow", String(data.conformity));
    await expect(risk.getByText("50%")).toBeVisible();
    await expect(risk.getByText(/2 de 4 análises concluídas com risco baixo/)).toBeVisible();
    await expect(meter.getByRole("progressbar")).toHaveCount(0);
  });

  test("shows secondary metrics with real values and sparklines", async ({ page }) => {
    const data = requireSeed();

    await page.goto("/painel");

    const summary = page.getByRole("region", { name: "Resumo do período" });
    await expect(summary).toBeVisible({ timeout: 20_000 });

    const analyzedRow = summary.getByText("Documentos analisados", { exact: true }).locator("..");
    const highRiskRow = summary.getByText("Alertas de risco alto", { exact: true }).locator("..");
    const pendingRow = summary.getByText("Comprovantes pendentes", { exact: true }).locator("..");

    await expect(
      analyzedRow.getByText(String(data.documents_analyzed), { exact: true }),
    ).toBeVisible();
    await expect(highRiskRow.getByText(String(data.high_risk), { exact: true })).toBeVisible();
    await expect(
      pendingRow.getByText(String(data.pending_receipts), { exact: true }),
    ).toBeVisible();

    await expect(summary.getByRole("img", { name: /Documentos analisados por dia/ })).toBeVisible();
    await expect(
      summary.getByRole("img", { name: /Análises em risco alto por dia/ }),
    ).toBeVisible();
    await expect(
      summary.getByRole("img", { name: /Comprovantes pendentes por vencimento/ }),
    ).toBeVisible();
  });

  test("recent analyses show honest fields and open the detail route", async ({ page }) => {
    const data = requireSeed();

    await page.goto("/painel");

    const recent = page.getByRole("region", { name: "Análises recentes" });
    await expect(recent).toBeVisible({ timeout: 20_000 });

    await expect(
      recent.getByText(/ainda não expõe número do documento, emissor, CNPJ e valor/),
    ).toBeVisible();

    const table = recent.getByRole("table", { name: "Análises recentes" });
    await expect(table).toBeVisible();

    const failedShort = data.analysis_ids.failed.slice(0, 8);
    const failedRow = table.getByRole("row", { name: new RegExp(failedShort) });
    await expect(failedRow).toContainText("Falhou");

    const processingShort = data.analysis_ids.processing.slice(0, 8);
    const processingRow = table.getByRole("row", { name: new RegExp(processingShort) });
    await expect(processingRow).toContainText("Em análise");

    const lowId = data.analysis_ids.completed[0];
    const lowRow = table.getByRole("row", { name: new RegExp(lowId.slice(0, 8)) });
    await expect(lowRow.getByRole("meter")).toHaveAttribute("aria-valuenow", "12");
    await expect(lowRow.getByText("Baixo").first()).toBeVisible();
    await expect(lowRow.getByText("Indisponível")).toHaveCount(3);

    const detailLink = lowRow.getByRole("link", {
      name: new RegExp(`Abrir análise ${lowId}`),
    });
    await expect(detailLink).toHaveAttribute("href", `/verificacao/${lowId}`);
    await expect(recent.getByRole("link", { name: "Ver todos" })).toHaveAttribute(
      "href",
      "/verificacao",
    );

    await detailLink.click();
    await expect(page).toHaveURL(new RegExp(`/verificacao/${lowId}$`), { timeout: 20_000 });
  });

  test("shows upcoming due dates in ascending order", async ({ page }) => {
    const data = requireSeed();

    await page.goto("/painel");

    const upcoming = page.getByRole("region", { name: "Próximos vencimentos" });
    const items = upcoming.locator("ul > li");

    await expect(items).toHaveCount(data.payables.length, { timeout: 20_000 });
    await expect(items.nth(0)).toContainText("Energia elétrica");
    await expect(items.nth(0)).toContainText("vencido há 2 dias");
    await expect(items.nth(0)).toContainText("Vencido");
    await expect(items.nth(0)).toContainText("184,75");
    await expect(items.nth(1)).toContainText("Internet");
    await expect(items.nth(1)).toContainText("vence hoje");
    await expect(items.nth(1)).toContainText("Aguardando confirmação");
    await expect(items.nth(1)).toContainText("129,90");
    await expect(items.nth(2)).toContainText("Aluguel");
    await expect(items.nth(2)).toContainText("em 3 dias");
    await expect(items.nth(2)).toContainText("2.500,00");
    await expect(items.nth(3)).toContainText("Água");
    await expect(items.nth(3)).toContainText("em 10 dias");
    await expect(items.nth(3)).toContainText("89,50");
    await expect(upcoming.getByRole("link", { name: "Ver todos" })).toHaveAttribute(
      "href",
      "/pagamentos",
    );
  });

  test("changes the distribution period and recalculates the summary", async ({ page }) => {
    const data = requireSeed();

    await page.goto("/painel");

    const distribution = page.getByRole("region", { name: "Distribuição de risco" });
    await expect(distribution).toBeVisible({ timeout: 20_000 });
    const sevenDays = distribution.getByRole("button", { name: "7 dias" });
    const thirtyDays = distribution.getByRole("button", { name: "30 dias" });

    await expect(thirtyDays).toHaveAttribute("aria-pressed", "true");
    await sevenDays.click();
    await expect(sevenDays).toHaveAttribute("aria-pressed", "true");

    await expect(
      distribution.getByRole("img", { name: /Distribuição de risco dos últimos 7 dias/ }),
    ).toBeVisible({ timeout: 20_000 });

    const risk = page.getByRole("region", { name: "Risco médio" });
    await expect(risk.getByRole("meter")).toHaveAttribute(
      "aria-valuenow",
      String(data.seven_day_average),
      { timeout: 20_000 },
    );

    const summary = page.getByRole("region", { name: "Resumo do período" });
    const analyzedRow = summary.getByText("Documentos analisados", { exact: true }).locator("..");
    const highRiskRow = summary.getByText("Alertas de risco alto", { exact: true }).locator("..");

    await expect(
      analyzedRow.getByText(String(data.seven_day_documents), { exact: true }),
    ).toBeVisible();
    await expect(
      highRiskRow.getByText(String(data.seven_day_high_risk), { exact: true }),
    ).toBeVisible();
  });

  test("updates title and favicon for high-risk alerts", async ({ page }) => {
    await page.goto("/painel");

    await expect
      .poll(() => page.title(), { timeout: 30_000 })
      .toMatch(/^\(2\) Painel Principal \| SentinelPay/);

    await expect(page.locator('link[rel="icon"]').first()).toHaveAttribute(
      "href",
      "/favicon-alert.svg",
    );
  });

  test("has no horizontal scroll with seeded data", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await page.goto("/painel");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByRole("region", { name: "Risco médio" })).toBeVisible({
      timeout: 30_000,
    });

    for (const width of [360, 768, 1440]) {
      await test.step(`width ${width}`, async () => {
        await page.setViewportSize({ width, height: 900 });

        const hasHorizontalScroll = await page.evaluate(
          () => document.documentElement.scrollWidth > window.innerWidth,
        );
        expect(hasHorizontalScroll).toBe(false);
      });
    }
  });
});

test.describe("dashboard with a new account", () => {
  test("shows the first document empty state without fake metrics", async ({ page, context }) => {
    test.skip(!available, skipReason);

    const baseURL = requireBaseUrl();
    const session = createBackendSession();

    await applySessionCookies(context, session, baseURL);
    await page.goto("/painel");

    await expect(page.getByRole("heading", { name: "Envie seu primeiro documento" })).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page.getByRole("link", { name: "Ir para a Central de Verificação" }),
    ).toHaveAttribute("href", "/verificacao");
    await expect(page.getByRole("region", { name: "Risco médio" })).toHaveCount(0);
    await expect(page.getByRole("meter")).toHaveCount(0);

    await expect
      .poll(() => page.title(), { timeout: 20_000 })
      .toMatch(/^Painel Principal \| SentinelPay/);
    await expect(page.locator('link[rel="icon"]').first()).toHaveAttribute("href", "/icon.svg");
  });
});
