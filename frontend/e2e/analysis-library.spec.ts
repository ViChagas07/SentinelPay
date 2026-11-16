import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import type { AnalysisListItem } from "@/lib/api/schemas";

import {
  analysisDetail,
  applyFakeSessionCookies,
  installFakeBackend,
  problem,
  type FakeResponse,
} from "./support/fake-backend";

const DAY_MS = 86_400_000;

function makeId(index: number): string {
  return `${index.toString(16).padStart(8, "0")}-0000-4000-8000-${index
    .toString(16)
    .padStart(12, "0")}`;
}

function createdAt(daysAgo: number): string {
  return new Date(Date.now() - daysAgo * DAY_MS).toISOString();
}

function item(
  index: number,
  kind: AnalysisListItem["kind"],
  status: AnalysisListItem["status"],
  score: number | null,
  band: AnalysisListItem["band"],
  daysAgo: number,
  errorCode: string | null = null,
): AnalysisListItem {
  return {
    id: makeId(index),
    status,
    kind,
    score,
    band,
    error_code: errorCode,
    created_at: createdAt(daysAgo),
    updated_at: createdAt(daysAgo),
  };
}

const BOLETOS: AnalysisListItem[] = [
  item(1, "boleto", "completed", 12, "low", 40),
  item(2, "boleto", "completed", 20, "low", 60),
  item(3, "boleto", "completed", 18, "low", 3),
  item(4, "boleto", "degraded", 30, "low", 4),
  item(5, "boleto", "completed", 45, "attention", 5),
  item(6, "boleto", "completed", 55, "attention", 6),
  item(7, "boleto", "completed", 60, "attention", 7),
  item(8, "boleto", "completed", 75, "high", 8),
  item(9, "boleto", "completed", 85, "high", 9),
  item(10, "boleto", "completed", 92, "high", 10),
  item(11, "boleto", "processing", null, null, 0.05),
  item(12, "boleto", "queued", null, null, 0.1),
  item(13, "boleto", "failed", null, null, 0.2, "analysis_failed"),
];

const PAYSLIPS: AnalysisListItem[] = [
  item(21, "payslip", "completed", 22, "low", 1),
  item(22, "payslip", "completed", 88, "high", 2),
  item(23, "payslip", "failed", null, null, 3, "analysis_failed"),
];

const ALL_ITEMS = [...BOLETOS, ...PAYSLIPS];

function listResponse(items: readonly AnalysisListItem[]): FakeResponse {
  return {
    status: 200,
    body: { items, next_cursor: null },
  };
}

function detailResponse(analysis: AnalysisListItem): FakeResponse {
  const score = analysis.score;
  const band = analysis.band;
  const result =
    score !== null && band !== null
      ? {
          score,
          band,
          base_score: score,
          llm_adjustment: 0,
          evidence: [],
          justification: "Justificativa sintética do teste.",
          inconsistencies: [],
          degradation_flags: [],
        }
      : null;

  return {
    status: 200,
    body: analysisDetail({
      id: analysis.id,
      status: analysis.status,
      kind: analysis.kind,
      created_at: analysis.created_at,
      updated_at: analysis.updated_at,
      error_code: analysis.error_code,
      result_available: result !== null,
      result,
    }),
  };
}

function findItem(analysisId: string): AnalysisListItem {
  const found = ALL_ITEMS.find((candidate) => candidate.id === analysisId);

  if (!found) {
    throw new Error(`Unknown analysis in the fake library: ${analysisId}`);
  }

  return found;
}

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

async function openLibrary(
  page: Page,
  context: BrowserContext,
  options: { items?: readonly AnalysisListItem[]; list?: FakeResponse; path: string },
): Promise<void> {
  await applyFakeSessionCookies(context, requireBaseUrl());
  await installFakeBackend(page, {
    list: options.list ?? listResponse(options.items ?? ALL_ITEMS),
    detail: (analysisId) => detailResponse(findItem(analysisId)),
  });
  await page.goto(options.path);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 20_000 });
}

test.describe("analysis library", () => {
  test("shows real counts for the whole sample and paginates by ten", async ({ page, context }) => {
    await openLibrary(page, context, { path: "/boletos" });

    await expect(page.getByText("01 / Boletos")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Boletos" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Nova verificação" })).toHaveAttribute(
      "href",
      "/verificacao?tipo=boleto",
    );

    const allTab = page.getByRole("tab", { name: /Todos/ });
    const lowTab = page.getByRole("tab", { name: /Baixo/ });
    const attentionTab = page.getByRole("tab", { name: /Médio/ });
    const highTab = page.getByRole("tab", { name: /Alto/ });

    await expect(allTab).toContainText("13");
    await expect(lowTab).toContainText("4");
    await expect(attentionTab).toContainText("3");
    await expect(highTab).toContainText("3");

    const panel = page.getByRole("tabpanel", { name: /Todos/ });
    const table = panel.getByRole("table", { name: "Lista de boletos analisados" });
    await expect(table.locator("tbody tr")).toHaveCount(10);
    await expect(table.getByText("Analisado com ressalvas")).toBeVisible();
    await expect(page.getByText("Página 1 de 2")).toBeVisible();

    await page.getByRole("button", { name: "Próxima página" }).click();
    await expect(page).toHaveURL(/[?&]page=2/);
    await expect(page.getByText("Página 2 de 2")).toBeVisible();
    await expect(table.locator("tbody tr")).toHaveCount(3);
    await expect(allTab).toContainText("13");

    await page.getByRole("button", { name: "Página anterior" }).click();
    await expect(page).toHaveURL(/\/boletos$/);
    await expect(table.locator("tbody tr")).toHaveCount(10);
  });

  test("keeps filters in the URL and offers a clear action for an empty result", async ({
    page,
    context,
  }) => {
    await openLibrary(page, context, { path: "/boletos" });

    await page.getByRole("combobox", { name: "Status do job" }).click();
    await page.getByRole("option", { name: "Falhou" }).click();

    await expect(page).toHaveURL(/[?&]status=failed/);
    const panel = page.getByRole("tabpanel", { name: /Todos/ });
    const table = panel.getByRole("table", { name: "Lista de boletos analisados" });
    await expect(table.locator("tbody tr")).toHaveCount(1);
    await expect(table.getByText("Falhou")).toBeVisible();
    await expect(page.getByRole("tab", { name: /Todos/ })).toContainText("1");

    await page.getByRole("tab", { name: /Alto/ }).click();
    await expect(page).toHaveURL(/[?&]band=high/);
    await expect(page).toHaveURL(/[?&]status=failed/);
    await expect(
      page.getByRole("heading", { name: "Nenhum resultado para estes filtros." }).first(),
    ).toBeVisible();

    await page.getByRole("button", { name: "Limpar filtros" }).first().click();
    await expect(page).toHaveURL(/\/boletos$/);
    await expect(table.locator("tbody tr")).toHaveCount(10);
    await expect(page.getByRole("tab", { name: /Todos/ })).toContainText("13");

    await page.getByRole("searchbox", { name: "Busca" }).fill("00000008");
    await page.getByRole("search").getByRole("button", { name: "Buscar" }).click();
    await expect(page).toHaveURL(/[?&]q=00000008/);
    await expect(table.locator("tbody tr")).toHaveCount(1);
    await expect(table.getByRole("link", { name: new RegExp(BOLETOS[7].id) })).toBeVisible();
  });

  test("navigates rows with the keyboard and opens the dossier from a filtered view", async ({
    page,
    context,
  }) => {
    await openLibrary(page, context, { path: "/boletos?band=high" });

    const panel = page.getByRole("tabpanel", { name: /Alto/ });
    const table = panel.getByRole("table", { name: "Lista de boletos analisados" });
    await expect(table.locator("tbody tr")).toHaveCount(3);

    const links = table.locator("a[data-analysis-row-link]");
    const first = links.nth(0);
    const second = links.nth(1);

    await first.focus();
    await expect(first).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(second).toBeFocused();

    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(new RegExp(`/verificacao/${BOLETOS[8].id}$`));
    await expect(page.getByRole("heading", { name: "Índice de risco" })).toBeVisible({
      timeout: 20_000,
    });
  });

  test("uses payslip columns, real counts and preselects the type in verification", async ({
    page,
    context,
  }) => {
    await openLibrary(page, context, { path: "/folha" });

    await expect(page.getByText("02 / Folha de pagamento")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Folha de pagamento" })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Todos/ })).toContainText("3");
    await expect(page.getByRole("tab", { name: /Baixo/ })).toContainText("1");
    await expect(page.getByRole("tab", { name: /Alto/ })).toContainText("1");

    const panel = page.getByRole("tabpanel", { name: /Todos/ });
    const table = panel.getByRole("table", { name: "Lista de contracheques analisados" });
    await expect(table.getByRole("columnheader", { name: "Empregador e CNPJ" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Competência" })).toBeVisible();
    await expect(table.getByRole("columnheader", { name: "Valor líquido" })).toBeVisible();
    await expect(table.getByText("Indisponível").first()).toBeVisible();

    await page.getByRole("link", { name: "Nova verificação" }).click();
    await expect(page).toHaveURL(/\/verificacao\?tipo=payslip$/);
    await expect(page.getByRole("combobox", { name: "Tipo do documento" })).toContainText(
      "Contracheque",
    );
  });

  test("updates an in-progress row when the job finishes", async ({ page, context }) => {
    const processing = item(31, "boleto", "processing", null, null, 0.01);
    const completed = {
      ...processing,
      status: "completed" as const,
      score: 72,
      band: "high" as const,
    };
    let requests = 0;

    await applyFakeSessionCookies(context, requireBaseUrl());
    await installFakeBackend(page, {
      list: () => {
        requests += 1;

        return listResponse(requests === 1 ? [processing] : [completed]);
      },
      detail: () => detailResponse(completed),
    });
    await page.goto("/boletos");

    const panel = page.getByRole("tabpanel", { name: /Todos/ });
    const table = panel.getByRole("table", { name: "Lista de boletos analisados" });

    await expect(table.getByText("Em análise")).toBeVisible({ timeout: 20_000 });
    await expect(panel.getByText("Em andamento: 1.")).toBeVisible();

    await expect(table.getByText("Analisado")).toBeVisible({ timeout: 15_000 });
    await expect(table.getByRole("meter")).toHaveAttribute("aria-valuenow", "72");
  });

  test("has no axe violations on the boleto list", async ({ page, context }) => {
    await openLibrary(page, context, { path: "/boletos" });

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    expect(results.violations).toEqual([]);
  });

  test("shows the first-verification invitation for an empty account", async ({
    page,
    context,
  }) => {
    await openLibrary(page, context, { path: "/boletos", items: [] });

    await expect(
      page.getByRole("heading", { name: "Nenhum boleto analisado ainda." }).first(),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Fazer a primeira verificação" })).toHaveAttribute(
      "href",
      "/verificacao?tipo=boleto",
    );
  });

  test("shows the error state with a retry action", async ({ page, context }) => {
    await openLibrary(page, context, {
      path: "/boletos",
      list: problem(500, "internal_error", "Falha ao listar análises."),
    });

    await expect(
      page.getByRole("heading", { name: "Não foi possível carregar." }).first(),
    ).toBeVisible();
    await expect(page.getByText("Não foi possível carregar as análises.").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
  });

  test("stacks the list on mobile with the full risk ruler and no horizontal scroll", async ({
    page,
    context,
  }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await openLibrary(page, context, { path: "/boletos" });

    const panel = page.getByRole("tabpanel", { name: /Todos/ });
    const mobileList = panel.getByRole("list", { name: "Lista de boletos analisados" });
    await expect(mobileList).toBeVisible();
    await expect(panel.locator("table")).toBeHidden();
    await expect(page.locator('[data-variant="medium"]:visible').first()).toBeVisible();

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
