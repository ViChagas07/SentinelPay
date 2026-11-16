import { expect, test } from "@playwright/test";

import {
  applySessionCookies,
  backendSessionAvailable,
  createBackendSession,
} from "./support/backend-session";
import { buildSyntheticBoletoPdf } from "./support/synthetic-pdf";

const available = backendSessionAvailable();
const skipReason = "API de testes indisponível: suba a stack com `docker compose up -d`.";

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

test.describe("verification flow with the real backend", () => {
  test("uploads a synthetic PDF, polls the job and resumes it after reload", async ({
    page,
    context,
  }) => {
    test.skip(!available, skipReason);
    test.setTimeout(120_000);

    const session = createBackendSession({
      email: `verificacao.${Date.now()}@paysentineliq.test`,
    });

    await applySessionCookies(context, session, requireBaseUrl());
    await page.goto("/verificacao");

    await expect(
      page.getByRole("heading", { name: "Envie o documento e acompanhe cada sinal." }),
    ).toBeVisible({ timeout: 20_000 });

    await expect(page.getByRole("button", { name: "Enviar para análise" })).toBeDisabled();
    await expect(
      page.getByText("Escolha o tipo do documento antes de enviar.").first(),
    ).toBeVisible();
    await expect(page.getByText(/Limite de 25 MB/)).toBeVisible();

    await page.getByRole("combobox", { name: "Tipo do documento" }).click();
    await page.getByRole("option", { name: "Boleto" }).click();

    await page.locator('input[type="file"]').setInputFiles({
      name: "boleto-sintetico.pdf",
      mimeType: "application/pdf",
      buffer: buildSyntheticBoletoPdf(
        "Boleto sintetico para teste de fluxo com texto nativo suficiente para leitura.",
      ),
    });

    await expect(page.getByText("boleto-sintetico.pdf")).toBeVisible();
    await expect(page.getByRole("button", { name: "Enviar para análise" })).toBeEnabled();
    await page.getByRole("button", { name: "Enviar para análise" }).click();

    await expect(page.getByRole("heading", { name: "Andamento da análise" })).toBeVisible({
      timeout: 40_000,
    });
    await expect(page.getByText(/Análise #[0-9a-f]{8}/).first()).toBeVisible();
    await expect(page.getByText("Etapas do backend")).toBeVisible();
    await expect(page.getByText("Leitura do documento")).toBeVisible();
    await expect(page.getByText("Extração de campos")).toBeVisible();
    await expect(page.getByText("Regras FEBRABAN, INSS e CLT")).toBeVisible();
    await expect(page.getByText(/Tempo decorrido/)).toBeVisible();

    const recent = page.getByRole("region", { name: "Verificações recentes" });
    await expect(recent).toBeVisible();
    const recentLink = recent.getByRole("link", { name: /Abrir análise/ }).first();

    await expect(recentLink).toBeVisible({ timeout: 40_000 });
    const href = await recentLink.getAttribute("href");
    const analysisId = href?.match(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
    )?.[0];

    expect(analysisId).toBeTruthy();

    await page.goto(`/verificacao/${analysisId}`);
    await expect(page.getByRole("heading", { level: 1, name: /Análise #[0-9a-f]{8}/ })).toBeVisible(
      {
        timeout: 30_000,
      },
    );

    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: /Análise #[0-9a-f]{8}/ })).toBeVisible(
      {
        timeout: 30_000,
      },
    );
    await expect(
      page
        .getByText(/Andamento da análise|Índice de risco|Resultado indisponível|A análise falhou/)
        .first(),
    ).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Documento não disponível pela API.")).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page.getByText(
        "O índice organiza sinais para revisão e não substitui a conferência dos dados nem decide sozinho.",
      ),
    ).toBeVisible();
  });
});
