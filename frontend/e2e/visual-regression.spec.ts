import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import type { AnalysisListItem } from "@/lib/api/schemas";

import {
  analysisDetail,
  applyFakeSessionCookies,
  installFakeBackend,
} from "./support/fake-backend";

const ANALYSIS_ID = "22222222-2222-4222-8222-222222222222";
const DAY_MS = 86_400_000;
const FIXED_TIME = new Date("2026-11-16T12:00:00Z");

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
    score: 55,
    band: "attention",
    error_code: null,
    created_at: new Date(Date.now() - 2 * DAY_MS).toISOString(),
    updated_at: new Date(Date.now() - 2 * DAY_MS).toISOString(),
  },
  {
    id: "44444444-4444-4444-8444-444444444444",
    status: "completed",
    kind: "boleto",
    score: 18,
    band: "low",
    error_code: null,
    created_at: new Date(Date.now() - 3 * DAY_MS).toISOString(),
    updated_at: new Date(Date.now() - 3 * DAY_MS).toISOString(),
  },
];

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
  options: { theme: "light" | "dark"; session: boolean },
): Promise<void> {
  const baseURL = requireBaseUrl();
  await context.clearCookies();

  if (options.session) {
    await applyFakeSessionCookies(context, baseURL);
  }

  await context.addCookies([
    { name: "locale", value: "pt", url: baseURL },
    { name: "theme", value: options.theme, url: baseURL },
  ]);
  await page.clock.setFixedTime(FIXED_TIME);
  await page.emulateMedia({
    reducedMotion: "reduce",
    colorScheme: options.theme === "dark" ? "dark" : "light",
  });
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
    payables: {
      status: 200,
      body: {
        items: [
          {
            id: "55555555-5555-4555-8555-555555555555",
            analysis_id: ANALYSIS_ID,
            description: "Fatura de serviço",
            amount: "248.70",
            due_date: new Date(FIXED_TIME.getTime() + 2 * DAY_MS).toISOString().slice(0, 10),
            status: "pending_confirmation",
            created_at: FIXED_TIME.toISOString(),
            updated_at: FIXED_TIME.toISOString(),
          },
        ],
        next_cursor: null,
      },
    },
    notifications: { status: 200, body: { items: [], next_cursor: null } },
    unreadCount: { status: 200, body: { unread: 0 } },
  });
}

for (const theme of ["light", "dark"] as const) {
  test(`regressao visual da landing (${theme})`, async ({ page, context }) => {
    await prepare(page, context, { theme, session: false });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 30_000 });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(400);

    await expect(page).toHaveScreenshot(`landing-${theme}.png`, {
      fullPage: true,
      animations: "disabled",
      caret: "hide",
      maxDiffPixelRatio: 0.02,
    });
  });

  test(`regressao visual do painel (${theme})`, async ({ page, context }) => {
    await prepare(page, context, { theme, session: true });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/painel");
    await expect(page.locator("section[aria-labelledby='dashboard-risk-title']")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.locator("section[aria-labelledby='dashboard-recent-title'] table"),
    ).toBeVisible({ timeout: 30_000 });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(400);

    await expect(page).toHaveScreenshot(`painel-${theme}.png`, {
      fullPage: true,
      animations: "disabled",
      caret: "hide",
      maxDiffPixelRatio: 0.02,
    });
  });
}
