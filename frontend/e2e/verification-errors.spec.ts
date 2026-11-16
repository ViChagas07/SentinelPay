import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type BrowserContext } from "@playwright/test";

import {
  analysisDetail,
  applyFakeSessionCookies,
  installFakeBackend,
  problem,
  type FakeBackendOptions,
} from "./support/fake-backend";
import { buildSyntheticBoletoPdf } from "./support/synthetic-pdf";

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

async function openPage(
  page: Page,
  context: BrowserContext,
  options: FakeBackendOptions = {},
  path = "/verificacao",
): Promise<void> {
  await applyFakeSessionCookies(context, requireBaseUrl());
  await installFakeBackend(page, options);
  await page.goto(path);
  await expect(page.getByRole("main")).toBeVisible({ timeout: 20_000 });
}

async function selectBoleto(page: Page): Promise<void> {
  await page.getByRole("combobox", { name: "Tipo do documento" }).click();
  await page.getByRole("option", { name: "Boleto" }).click();
}

async function selectPdf(
  page: Page,
  buffer = buildSyntheticBoletoPdf("Boleto sintetico para teste."),
): Promise<void> {
  await page.locator('input[type="file"]').setInputFiles({
    name: "boleto-sintetico.pdf",
    mimeType: "application/pdf",
    buffer,
  });
}

test.describe("verification upload validation", () => {
  test("requires the type and rejects unsupported files before sending", async ({
    page,
    context,
  }) => {
    await openPage(page, context);

    const submit = page.getByRole("button", { name: "Enviar para análise" });
    await expect(submit).toBeDisabled();
    await expect(page.getByRole("combobox", { name: "Tipo do documento" })).toContainText(
      "Selecione o tipo",
    );
    await expect(
      page.getByText("Escolha o tipo do documento antes de enviar.").first(),
    ).toBeVisible();

    await page.locator('input[type="file"]').setInputFiles({
      name: "nota.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("texto simples"),
    });

    await expect(page.getByText("Formato não aceito. Envie PDF, PNG ou JPEG.")).toBeVisible();
    await expect(submit).toBeDisabled();

    await page.getByRole("button", { name: "Remover arquivo" }).click();
    await selectPdf(page);
    await expect(page.getByText("boleto-sintetico.pdf")).toBeVisible();
    await expect(submit).toBeDisabled();

    await selectBoleto(page);
    await expect(submit).toBeEnabled();
  });

  test("rejects files above the backend limit on the client", async ({ page, context }) => {
    await openPage(page, context);

    await page.locator('input[type="file"]').setInputFiles({
      name: "arquivo-grande.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.alloc(26 * 1024 * 1024, 0x20),
    });

    await expect(page.getByText(/O arquivo tem/)).toBeVisible();
    await expect(page.getByText(/limite aceito/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Enviar para análise" })).toBeDisabled();
  });

  test("shows the server rejection for an unsupported document", async ({ page, context }) => {
    await openPage(page, context, {
      create: problem(422, "unsupported_document_type", "Tipo de documento não suportado."),
    });

    await selectBoleto(page);
    await selectPdf(page);
    await page.getByRole("button", { name: "Enviar para análise" }).click();

    await expect(page.getByText("O envio não terminou.")).toBeVisible();
    await expect(page.getByText("Formato não aceito. Envie PDF, PNG ou JPEG.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Enviar para análise" })).toBeEnabled();
  });

  test("shows the server rejection for an oversized upload", async ({ page, context }) => {
    await openPage(page, context, {
      create: problem(413, "upload_too_large", "Upload acima do limite."),
    });

    await selectBoleto(page);
    await selectPdf(page);
    await page.getByRole("button", { name: "Enviar para análise" }).click();

    await expect(page.getByText("O envio não terminou.")).toBeVisible();
    await expect(page.getByText("O arquivo excede o limite aceito.")).toBeVisible();
  });

  test("has no axe violations on the upload page", async ({ page, context }) => {
    await openPage(page, context);
    await selectBoleto(page);
    await selectPdf(page);

    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });

  test("does not overflow the viewport on a narrow screen", async ({ page, context }) => {
    const analysisId = "99999999-9999-4999-8999-999999999999";

    await page.setViewportSize({ width: 360, height: 900 });
    await openPage(
      page,
      context,
      {
        detail: (id) => ({ status: 200, body: analysisDetail({ id }) }),
      },
      "/verificacao",
    );

    await expect(
      page.getByRole("heading", { name: "Envie o documento e acompanhe cada sinal." }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
      ),
    ).toBe(true);

    await page.goto(`/verificacao/${analysisId}`);
    await expect(page.getByRole("heading", { name: "Índice de risco" })).toBeVisible({
      timeout: 20_000,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
      ),
    ).toBe(true);
  });
});

test.describe("verification dossier states", () => {
  test("shows the real pipeline while the job is processing", async ({ page, context }) => {
    const createdAt = new Date(Date.now() - 30_000).toISOString();
    const analysisId = "33333333-3333-4333-8333-333333333333";

    await openPage(
      page,
      context,
      {
        detail: (id) => ({
          status: 200,
          body: analysisDetail({
            id,
            status: "processing",
            created_at: createdAt,
            updated_at: createdAt,
            error_code: null,
            result_available: false,
            result: null,
          }),
        }),
      },
      `/verificacao/${analysisId}`,
    );

    await expect(page.getByRole("heading", { level: 1, name: "Análise #33333333" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Andamento da análise" })).toBeVisible();
    await expect(page.getByText("Em análise").first()).toBeVisible();
    await expect(page.getByText("Tempo decorrido")).toBeVisible();
    const progress = page.getByRole("progressbar", { name: "Progresso da análise" });
    await expect(progress).toHaveAttribute(
      "aria-valuetext",
      "O backend não informa percentual. A análise continua no servidor.",
    );
    await expect(page.getByText("Etapas do backend")).toBeVisible();
    await expect(page.getByText("Execução da análise")).toBeVisible();
    await expect(page.getByText("Leitura do documento")).toBeVisible();
    await expect(page.getByText("Extração de campos")).toBeVisible();
    await expect(page.getByText("Regras FEBRABAN, INSS e CLT")).toBeVisible();
    await expect(page.getByText("Classificação de risco")).toBeVisible();
    await expect(page.getByText("Justificativa")).toBeVisible();
  });

  test("shows the failed job with the translated error code", async ({ page, context }) => {
    const analysisId = "44444444-4444-4444-8444-444444444444";

    await openPage(
      page,
      context,
      {
        detail: (id) => ({
          status: 200,
          body: analysisDetail({
            id,
            status: "failed",
            error_code: "analysis_timeout",
            result_available: false,
            result: null,
          }),
        }),
      },
      `/verificacao/${analysisId}`,
    );

    await expect(page.getByText("A análise falhou.").first()).toBeVisible();
    await expect(page.getByText("A análise excedeu o tempo limite.")).toBeVisible();
    await expect(page.getByText("Código do erro: analysis_timeout")).toBeVisible();
    await expect(page.getByRole("button", { name: "Verificar novamente" })).toBeVisible();
    await expect(page.getByText("Índice de risco")).toHaveCount(0);
  });

  test("does not turn an unavailable result into low risk", async ({ page, context }) => {
    const analysisId = "55555555-5555-4555-8555-555555555555";

    await openPage(
      page,
      context,
      {
        detail: (id) => ({
          status: 200,
          body: analysisDetail({
            id,
            status: "completed",
            result_available: false,
            result: null,
          }),
        }),
      },
      `/verificacao/${analysisId}`,
    );

    await expect(page.getByText("Resultado indisponível.")).toBeVisible();
    await expect(page.getByText(/Isso não significa risco baixo/)).toBeVisible();
    await expect(page.getByRole("meter")).toHaveCount(0);
    await expect(page.getByText("Documento não disponível pela API.")).toBeVisible();
  });

  test("renders score, class, evidence, metadata and honest gaps", async ({ page, context }) => {
    const analysisId = "66666666-6666-4666-8666-666666666666";

    await openPage(
      page,
      context,
      {
        detail: (id) => ({
          status: 200,
          body: analysisDetail({ id }),
        }),
      },
      `/verificacao/${analysisId}`,
    );

    await expect(page.getByRole("heading", { name: "Índice de risco" })).toBeVisible();
    await expect(page.getByRole("meter")).toHaveAttribute("aria-valuenow", "82");
    await expect(page.getByText("Alto").first()).toBeVisible();
    await expect(
      page.getByText("A linha digitável não fecha com o dígito verificador conferido."),
    ).toBeVisible();
    await expect(page.getByText("Dígito verificador inválido")).toBeVisible();
    await expect(page.getByText("FEBRABAN").first()).toBeVisible();
    await expect(page.getByText("Campos extraídos indisponíveis.")).toBeVisible();
    await expect(page.getByText("Não informado pela API").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Copiar link" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Baixar relatório" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Marcar como revisado" })).toHaveCount(0);
    await expect(
      page.getByText(
        "O índice organiza sinais para revisão e não substitui a conferência dos dados nem decide sozinho.",
      ),
    ).toBeVisible();
  });

  test("shows a retry state when the detail request fails", async ({ page, context }) => {
    const analysisId = "77777777-7777-4777-8777-777777777777";

    await openPage(
      page,
      context,
      {
        detail: () => problem(500, "internal_error", "Falha interna de teste."),
      },
      `/verificacao/${analysisId}`,
    );

    await expect(page.getByText("Não foi possível carregar o dossiê.")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByRole("button", { name: "Verificar novamente" })).toBeVisible();
  });

  test("shows a not found state for an unknown analysis", async ({ page, context }) => {
    const analysisId = "88888888-8888-4888-8888-888888888888";

    await openPage(page, context, {}, `/verificacao/${analysisId}`);

    await expect(page.getByText("Análise não encontrada.")).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Ir para a Central de Verificação" }).first(),
    ).toBeVisible();
  });
});
