import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  analysisDetail,
  applyFakeSessionCookies,
  installFakeBackend,
  type FakeResponse,
} from "./support/fake-backend";
import type { PayableStatus } from "@/lib/api/schemas";

const DAY_MS = 86_400_000;
const RECEIPT_ANALYSIS_ID = "80000000-0000-4000-8000-000000000008";

type PayableFixture = {
  id: string;
  analysis_id: string;
  description: string;
  amount: string;
  due_date: string;
  status: PayableStatus;
  created_at: string;
  updated_at: string;
};

function dateFromToday(days: number): string {
  const date = new Date(Date.now() + days * DAY_MS);
  date.setUTCHours(12, 0, 0, 0);

  return date.toISOString().slice(0, 10);
}

function payable(
  index: number,
  description: string,
  amount: string,
  days: number,
  status: PayableStatus,
): PayableFixture {
  const id = `${String(index).padStart(8, "0")}-0000-4000-8000-${String(index).padStart(12, "0")}`;

  return {
    id,
    analysis_id: "11111111-1111-4111-8111-111111111111",
    description,
    amount,
    due_date: dateFromToday(days),
    status,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

const INITIAL_PAYABLES: PayableFixture[] = [
  payable(1, "Conta de energia", "248.70", 0, "pending"),
  payable(2, "Conta de água", "96.40", 3, "pending_confirmation"),
  payable(3, "Internet fibra", "129.90", -2, "overdue"),
  payable(4, "Gás encanado", "78.20", 10, "pending"),
  payable(5, "Condomínio", "650.00", -10, "paid"),
  payable(6, "Seguro residencial", "89.90", 20, "dismissed"),
];

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

type PaymentsHarness = {
  payables: PayableFixture[];
  reminderPreferences: {
    offsets_days: number[];
    local_time: string;
    channels: string[];
    timezone: string;
  };
};

async function openPayments(
  page: Page,
  context: BrowserContext,
  options: { path?: string; payables?: PayableFixture[] } = {},
): Promise<PaymentsHarness> {
  const baseURL = requireBaseUrl();
  const harness: PaymentsHarness = {
    payables: (options.payables ?? INITIAL_PAYABLES).map((item) => ({ ...item })),
    reminderPreferences: {
      offsets_days: [3, 1, 0],
      local_time: "09:00:00",
      channels: ["in_app"],
      timezone: "UTC",
    },
  };

  function listPayables(url: URL): FakeResponse {
    const statuses = url.searchParams.getAll("status");
    const items = statuses.length
      ? harness.payables.filter((item) => statuses.includes(item.status))
      : harness.payables;

    return {
      status: 200,
      body: {
        items: [...items].sort((left, right) => left.due_date.localeCompare(right.due_date)),
        next_cursor: null,
      },
    };
  }

  await applyFakeSessionCookies(context, baseURL);
  await installFakeBackend(page, {
    payables: listPayables,
    payableAction: (payableId, action) => {
      const item = harness.payables.find((candidate) => candidate.id === payableId);

      if (!item) {
        return { status: 404, body: { code: "payable_not_found" } };
      }

      item.status =
        action === "pay"
          ? "paid"
          : action === "confirm"
            ? "pending"
            : action === "dismiss"
              ? "dismissed"
              : item.status;
      item.updated_at = new Date().toISOString();

      return { status: 200, body: item };
    },
    payableDueDate: (payableId, dueDate) => {
      const item = harness.payables.find((candidate) => candidate.id === payableId);

      if (!item) {
        return { status: 404, body: { code: "payable_not_found" } };
      }

      item.due_date = dueDate;
      item.updated_at = new Date().toISOString();

      return { status: 200, body: item };
    },
    reminderPreferences: () => ({
      status: 200,
      body: harness.reminderPreferences,
    }),
    updateReminderPreferences: (body) => {
      const parsed = body as {
        offsets_days?: number[];
        local_time?: string;
        channels?: string[];
      };

      harness.reminderPreferences = {
        offsets_days: parsed.offsets_days ?? harness.reminderPreferences.offsets_days,
        local_time: parsed.local_time ?? harness.reminderPreferences.local_time,
        channels: parsed.channels ?? harness.reminderPreferences.channels,
        timezone: "UTC",
      };

      return { status: 200, body: harness.reminderPreferences };
    },
    create: () => ({
      status: 202,
      body: { analysis_id: RECEIPT_ANALYSIS_ID, status: "queued" },
    }),
    detail: (analysisId) => ({
      status: 200,
      body: analysisDetail({
        id: analysisId,
        kind: "receipt",
        status: "queued",
        result_available: false,
        result: null,
      }),
    }),
  });
  await page.goto(options.path ?? "/pagamentos");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 20_000 });

  return harness;
}

test.describe("payments", () => {
  test("shows the real payable sample, timeline and paid/reschedule actions", async ({
    page,
    context,
  }) => {
    const harness = await openPayments(page, context);

    await expect(page.getByText("03 / Central de pagamentos")).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 1, name: "Central de pagamentos" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Cadastrar recibo" })).toBeVisible();

    const summary = page.getByRole("region", {
      name: "Contagens dos vencimentos ativos carregados da API.",
    });
    await expect(summary.getByText("A vencer")).toBeVisible();
    await expect(summary.getByText("Vence hoje")).toBeVisible();
    await expect(summary.getByText("Em atraso")).toBeVisible();

    const timeline = page.getByRole("list", {
      name: "Linha do tempo dos próximos vencimentos",
    });
    await expect(timeline.getByRole("button")).toHaveCount(3);

    const table = page.getByRole("table", { name: "Lista de contas e recibos" });
    await expect(table.locator("tbody tr")).toHaveCount(4);
    await expect(table.getByText("Conta de energia")).toBeVisible();
    await expect(table.getByText("Conta de água")).toBeVisible();
    await expect(table.getByText("Internet fibra")).toBeVisible();
    await expect(table.getByText("Vencido", { exact: true })).toBeVisible();
    await expect(table.getByText("Vence hoje", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Ações do vencimento: Conta de água" }).click();
    await page.getByRole("menuitem", { name: "Marcar como pago" }).click();

    const payDialog = page.getByRole("dialog");
    await expect(payDialog.getByRole("heading", { name: "Marcar como pago?" })).toBeVisible();
    await payDialog.getByRole("button", { name: "Marcar como pago" }).click();
    await expect(page.getByText("Vencimento marcado como pago.")).toBeVisible();

    await page.getByRole("combobox", { name: "Situação" }).click();
    await page.getByRole("option", { name: "Pagas" }).click();
    await expect(table.locator("tbody tr")).toHaveCount(2);
    await expect(table.getByText("Conta de água")).toBeVisible();
    await expect(table.getByText("Pago").first()).toBeVisible();

    await page.getByRole("combobox", { name: "Situação" }).click();
    await page.getByRole("option", { name: "Em aberto" }).click();
    await page.getByRole("button", { name: "Ações do vencimento: Conta de energia" }).click();
    await page.getByRole("menuitem", { name: "Ajustar vencimento" }).click();

    const rescheduleDialog = page.getByRole("dialog");
    await rescheduleDialog.getByLabel("Novo vencimento").fill(dateFromToday(5));
    await rescheduleDialog.getByRole("button", { name: "Salvar data" }).click();
    await expect(page.getByText("Vencimento atualizado.")).toBeVisible();
    await expect(table.getByText("em 5 dias")).toBeVisible();

    await page.getByRole("button", { name: "Ações do vencimento: Gás encanado" }).click();
    await expect(page.getByRole("menuitem", { name: "Excluir" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await page.keyboard.press("Escape");
    await expect(page.getByText("A API ainda não permite excluir vencimentos.")).toBeVisible();

    await page.goto(`${requireBaseUrl()}/pagamentos?vencimento=${harness.payables[4]?.id}`);
    await expect(page.getByText("Vencimento da notificação").first()).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText("Condomínio").first()).toBeVisible();
  });

  test("persists reminder preferences and sends a receipt through the real upload path", async ({
    page,
    context,
  }) => {
    const harness = await openPayments(page, context);

    await page.getByLabel("Antecedência em dias").fill("7, 1, 0");
    await page.getByLabel("Horário local").fill("08:30");
    await page.getByRole("button", { name: "Salvar lembretes" }).click();
    await expect(page.getByText("Lembretes atualizados.")).toBeVisible();
    expect(harness.reminderPreferences.offsets_days).toEqual([7, 1, 0]);
    expect(harness.reminderPreferences.local_time).toBe("08:30:00");

    await page.reload();
    await expect(page.getByLabel("Antecedência em dias")).toHaveValue("7, 1, 0");
    await expect(page.getByLabel("Horário local")).toHaveValue("08:30");

    await page.getByRole("button", { name: "Cadastrar recibo" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "Cadastrar recibo" })).toBeVisible();
    await expect(dialog.getByLabel("Tipo")).toHaveValue("Recibo");
    await expect(dialog.getByLabel("Emissor")).toHaveAttribute(
      "placeholder",
      "Extraído após a análise",
    );

    await dialog.getByRole("button", { name: "Enviar recibo" }).click();
    await expect(
      dialog
        .getByText(
          "O arquivo é obrigatório. A API só cria vencimentos a partir do recibo analisado.",
        )
        .first(),
    ).toBeVisible();

    await dialog.locator('input[type="file"]').setInputFiles({
      name: "recibo.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4\n%%EOF"),
    });
    await dialog.getByRole("button", { name: "Enviar recibo" }).click();

    await expect(page).toHaveURL(new RegExp(`/verificacao/${RECEIPT_ANALYSIS_ID}$`), {
      timeout: 20_000,
    });
  });

  test("stacks payable cards on mobile without page overflow", async ({ page, context }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await openPayments(page, context);

    const mobileList = page.getByRole("list", { name: "Lista de contas e recibos" });
    await expect(mobileList).toBeVisible();
    await expect(page.locator("table")).toBeHidden();
    await expect(mobileList.getByText("Conta de energia")).toBeVisible();

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

  test("has no axe violations on payments and the receipt dialog", async ({ page, context }) => {
    await openPayments(page, context);

    const pageResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(pageResults.violations).toEqual([]);

    await page.getByRole("button", { name: "Cadastrar recibo" }).click();
    const dialogResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(dialogResults.violations).toEqual([]);
  });

  test("shows an honest empty state without invented payables", async ({ page, context }) => {
    await openPayments(page, context, { payables: [] });

    await expect(
      page.getByRole("heading", { name: "Nenhum vencimento nesta visão." }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Cadastrar recibo" }).first()).toBeVisible();
  });
});
