import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import type { AnalysisListItem } from "@/lib/api/schemas";

import {
  analysisDetail,
  applyFakeSessionCookies,
  installFakeBackend,
} from "./support/fake-backend";

const WIDTHS = [360, 768, 1280, 1920] as const;
const DAY_MS = 86_400_000;
const ANALYSIS_ID = "22222222-2222-4222-8222-222222222222";

const ITEMS: AnalysisListItem[] = [
  {
    id: ANALYSIS_ID,
    status: "completed",
    kind: "boleto",
    score: 82,
    band: "high",
    error_code: null,
    created_at: new Date(Date.now() - DAY_MS).toISOString(),
    updated_at: new Date(Date.now() - DAY_MS).toISOString(),
  },
  {
    id: "33333333-3333-4333-8333-333333333333",
    status: "completed",
    kind: "payslip",
    score: 24,
    band: "low",
    error_code: null,
    created_at: new Date(Date.now() - 2 * DAY_MS).toISOString(),
    updated_at: new Date(Date.now() - 2 * DAY_MS).toISOString(),
  },
];

const ROUTES = [
  { path: "/", private: false },
  { path: "/login", private: false },
  { path: "/termos", private: false },
  { path: "/privacidade", private: false },
  { path: "/suporte", private: false },
  { path: "/servico-indisponivel", private: false },
  { path: "/painel", private: true },
  { path: "/verificacao", private: true },
  { path: "/verificacao/nova", private: true },
  { path: `/verificacao/${ANALYSIS_ID}`, private: true },
  { path: "/boletos", private: true },
  { path: "/folha", private: true },
  { path: "/pagamentos", private: true },
  { path: "/notificacoes", private: true },
  { path: "/account", private: true },
  { path: "/inteligencia", private: true },
] as const;

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

async function prepare(
  page: Page,
  context: BrowserContext,
  options: { session: boolean },
): Promise<void> {
  const baseURL = requireBaseUrl();
  await context.clearCookies();

  if (options.session) {
    await applyFakeSessionCookies(context, baseURL);
  }

  await context.addCookies([{ name: "locale", value: "pt", url: baseURL }]);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await installFakeBackend(page, {
    list: { status: 200, body: { items: ITEMS, next_cursor: null } },
    detail: (analysisId) => ({
      status: 200,
      body: analysisDetail({
        id: analysisId,
        result: {
          score: 82,
          band: "high",
          base_score: 80,
          llm_adjustment: 2,
          evidence: [],
          justification: "A linha digitável não fecha com o dígito verificador conferido.",
          inconsistencies: [],
          degradation_flags: [],
        },
      }),
    }),
    payables: { status: 200, body: { items: [], next_cursor: null } },
    notifications: { status: 200, body: { items: [], next_cursor: null } },
  });
}

async function assertNoHorizontalScroll(page: Page, label: string): Promise<void> {
  const metrics = await page.evaluate(() => {
    const documentElement = document.documentElement;

    return {
      scrollWidth: documentElement.scrollWidth,
      clientWidth: documentElement.clientWidth,
      bodyScrollWidth: document.body.scrollWidth,
    };
  });

  expect(
    metrics.scrollWidth,
    `${label}: scroll horizontal em ${metrics.scrollWidth}px de ${metrics.clientWidth}px`,
  ).toBeLessThanOrEqual(metrics.clientWidth + 1);
  expect(metrics.bodyScrollWidth, `${label}: body mais largo que a viewport`).toBeLessThanOrEqual(
    metrics.clientWidth + 1,
  );
}

async function assertRiskRulerComplete(page: Page, label: string): Promise<void> {
  await expect(page.locator('[role="meter"]').first()).toBeVisible({ timeout: 20_000 });

  const metrics = await page.evaluate(() => {
    const meter = document.querySelector('[role="meter"]');

    if (!meter) {
      return null;
    }

    const track = meter.querySelector<HTMLElement>(":scope > div");

    if (!track) {
      return null;
    }

    const segments = Array.from(track.querySelectorAll<HTMLElement>(":scope > span")).map(
      (segment) => segment.getBoundingClientRect().width,
    );
    const trackRect = track.getBoundingClientRect();
    const meterRect = meter.getBoundingClientRect();

    return {
      segments,
      segmentSum: segments.reduce((total, width) => total + width, 0),
      trackWidth: trackRect.width,
      trackScrollWidth: track.scrollWidth,
      trackClientWidth: track.clientWidth,
      meterLeft: meterRect.left,
      meterRight: meterRect.right,
      viewportWidth: window.innerWidth,
    };
  });

  expect(metrics, `${label}: regua de risco ausente`).not.toBeNull();

  if (!metrics) {
    return;
  }

  expect(metrics.segments, `${label}: regua sem as tres faixas`).toHaveLength(3);
  expect(
    Math.abs(metrics.segmentSum - metrics.trackWidth),
    `${label}: faixas nao preenchem a regua`,
  ).toBeLessThanOrEqual(3);
  expect(metrics.trackScrollWidth, `${label}: regua com rolagem interna`).toBeLessThanOrEqual(
    metrics.trackClientWidth + 1,
  );
  expect(metrics.meterLeft, `${label}: regua comeca fora da tela`).toBeGreaterThanOrEqual(-1);
  expect(metrics.meterRight, `${label}: regua termina fora da tela`).toBeLessThanOrEqual(
    metrics.viewportWidth + 1,
  );
}

for (const route of ROUTES) {
  test(`responsivo: ${route.path}`, async ({ page, context }) => {
    await prepare(page, context, { session: route.private });

    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: width >= 1280 ? 1080 : 900 });
      await page.goto(route.path);
      await expect(page.locator("main#conteudo, main").first()).toBeVisible({ timeout: 30_000 });
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(200);
      await assertNoHorizontalScroll(page, `${route.path}@${width}`);
    }
  });
}

test("regua de risco completa no painel em 360, 768, 1280 e 1920", async ({ page, context }) => {
  await prepare(page, context, { session: true });

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: width >= 1280 ? 1080 : 900 });
    await page.goto("/painel");
    await expect(page.locator("section[aria-labelledby='dashboard-risk-title']")).toBeVisible({
      timeout: 30_000,
    });
    await assertNoHorizontalScroll(page, `/painel@${width}`);
    await assertRiskRulerComplete(page, `/painel@${width}`);
  }
});

test("regua de risco completa no dossie em 360, 768, 1280 e 1920", async ({ page, context }) => {
  await prepare(page, context, { session: true });

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: width >= 1280 ? 1080 : 900 });
    await page.goto(`/verificacao/${ANALYSIS_ID}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 30_000 });
    await assertNoHorizontalScroll(page, `/verificacao/[id]@${width}`);
    await assertRiskRulerComplete(page, `/verificacao/[id]@${width}`);
  }
});
