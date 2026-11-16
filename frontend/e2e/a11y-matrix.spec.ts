import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import type { AnalysisListItem } from "@/lib/api/schemas";

import {
  analysisDetail,
  applyFakeSessionCookies,
  installFakeBackend,
  type FakeBackendOptions,
} from "./support/fake-backend";

const DAY_MS = 86_400_000;
const THEMES = ["light", "dark"] as const;
const LOCALES = ["pt", "es", "en"] as const;

const ANALYSIS_IDS = [
  "22222222-2222-4222-8222-222222222222",
  "33333333-3333-4333-8333-333333333333",
  "44444444-4444-4444-8444-444444444444",
];

function isoDaysAgo(days: number): string {
  return new Date(Date.now() - days * DAY_MS).toISOString();
}

function listItem(
  index: number,
  kind: AnalysisListItem["kind"],
  score: number,
  band: AnalysisListItem["band"],
  daysAgo: number,
): AnalysisListItem {
  return {
    id: ANALYSIS_IDS[index] ?? ANALYSIS_IDS[0],
    status: "completed",
    kind,
    score,
    band,
    error_code: null,
    created_at: isoDaysAgo(daysAgo),
    updated_at: isoDaysAgo(daysAgo),
  };
}

const LIST_ITEMS: AnalysisListItem[] = [
  listItem(0, "boleto", 82, "high", 1),
  listItem(1, "payslip", 55, "attention", 2),
  listItem(2, "boleto", 18, "low", 3),
];

const PAYABLES = [
  {
    id: "55555555-5555-4555-8555-555555555555",
    analysis_id: ANALYSIS_IDS[0],
    description: "Fatura de serviço",
    amount: "248.70",
    due_date: new Date(Date.now() + 2 * DAY_MS).toISOString().slice(0, 10),
    status: "pending_confirmation",
    created_at: isoDaysAgo(1),
    updated_at: isoDaysAgo(1),
  },
  {
    id: "66666666-6666-4666-8666-666666666666",
    analysis_id: ANALYSIS_IDS[1],
    description: "Conta mensal",
    amount: "96.40",
    due_date: new Date().toISOString().slice(0, 10),
    status: "pending",
    created_at: isoDaysAgo(2),
    updated_at: isoDaysAgo(2),
  },
];

const NOTIFICATIONS = [
  {
    id: "77777777-7777-4777-8777-777777777777",
    type: "high_risk_detected",
    payload: {
      analysis_id: ANALYSIS_IDS[0],
      document_type: "boleto",
      score: "82",
      band: "high",
    },
    read: false,
    read_at: null,
    created_at: isoDaysAgo(1),
  },
  {
    id: "88888888-8888-4888-8888-888888888888",
    type: "payable_due_soon",
    payload: {
      payable_id: PAYABLES[0].id,
      due_date: PAYABLES[0].due_date,
      days: "2",
    },
    read: true,
    read_at: isoDaysAgo(1),
    created_at: isoDaysAgo(2),
  },
];

function backendOptions(): FakeBackendOptions {
  return {
    list: { status: 200, body: { items: LIST_ITEMS, next_cursor: null } },
    detail: (analysisId) => ({
      status: 200,
      body: analysisDetail({
        id: analysisId,
        result: {
          score: 82,
          band: "high",
          base_score: 80,
          llm_adjustment: 2,
          evidence: [
            {
              rule_id: "boleto.dv_invalid",
              severity: "critical",
              weight: 70,
              message_key: "boleto.dv_invalid",
              source: "knowledge/febraban/manual_febraban_v1.pdf#1.5",
            },
            {
              rule_id: "boleto.utility_line_not_verifiable",
              severity: "info",
              weight: 0,
              message_key: "boleto.utility_line_not_verifiable",
              source: "knowledge/layouts/layout_v1.pdf#2",
            },
          ],
          justification: "A linha digitável não fecha com o dígito verificador conferido.",
          inconsistencies: ["O valor extraído diverge da linha digitável."],
          degradation_flags: [],
        },
      }),
    }),
    payables: { status: 200, body: { items: PAYABLES, next_cursor: null } },
    notifications: { status: 200, body: { items: NOTIFICATIONS, next_cursor: null } },
    unreadCount: { status: 200, body: { unread: 1 } },
  };
}

type RouteCase = {
  path: string;
  private: boolean;
  waitFor?: (page: Page) => Promise<void>;
};

const ROUTES: RouteCase[] = [
  { path: "/", private: false },
  { path: "/login", private: false },
  { path: "/termos", private: false },
  { path: "/privacidade", private: false },
  { path: "/suporte", private: false },
  { path: "/servico-indisponivel", private: false },
  { path: "/painel", private: true },
  { path: "/verificacao", private: true },
  { path: "/verificacao/nova", private: true },
  { path: `/verificacao/${ANALYSIS_IDS[0]}`, private: true },
  { path: "/boletos", private: true },
  { path: "/folha", private: true },
  { path: "/pagamentos", private: true },
  { path: "/notificacoes", private: true },
  { path: "/account", private: true },
  { path: "/inteligencia", private: true },
];

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

async function preparePage(
  page: Page,
  context: BrowserContext,
  options: { locale: (typeof LOCALES)[number]; theme: (typeof THEMES)[number]; session: boolean },
): Promise<void> {
  const baseURL = requireBaseUrl();
  await context.clearCookies();

  if (options.session) {
    await applyFakeSessionCookies(context, baseURL);
  }

  await context.addCookies([
    { name: "locale", value: options.locale, url: baseURL },
    { name: "theme", value: options.theme, url: baseURL },
  ]);
  await page.emulateMedia({
    reducedMotion: "reduce",
    colorScheme: options.theme === "dark" ? "dark" : "light",
  });
  await installFakeBackend(page, backendOptions());
}

async function waitForRoute(page: Page): Promise<void> {
  await expect(page.locator("main#conteudo, main").first()).toBeVisible({ timeout: 30_000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(250);
}

for (const route of ROUTES) {
  test(`axe matrix: ${route.path}`, async ({ page, context }) => {
    const violations: string[] = [];

    for (const theme of THEMES) {
      for (const locale of LOCALES) {
        await preparePage(page, context, { theme, locale, session: route.private });
        await page.goto(route.path);
        await waitForRoute(page);

        const results = await new AxeBuilder({ page }).analyze();

        if (results.violations.length > 0) {
          violations.push(
            ...results.violations.map(
              (violation) =>
                `${theme}/${locale} ${violation.id}: ${violation.help} (${violation.nodes.length} nos)`,
            ),
          );
        }
      }
    }

    expect(violations, `Violacoes em ${route.path}`).toEqual([]);
  });
}

test("axe matrix: 404 route", async ({ page, context }) => {
  await preparePage(page, context, { theme: "light", locale: "pt", session: false });
  await page.goto("/rota-que-nao-existe");
  await waitForRoute(page);

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("prefers-reduced-motion is honored on the landing hero", async ({ page, context }) => {
  await preparePage(page, context, { theme: "light", locale: "pt", session: false });
  await page.goto("/");
  await waitForRoute(page);

  const matches = await page.evaluate(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  expect(matches).toBe(true);
});
