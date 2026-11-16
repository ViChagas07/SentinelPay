import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  applyFakeSessionCookies,
  FAKE_USER,
  installFakeBackend,
  type FakeResponse,
} from "./support/fake-backend";

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

async function openAccount(
  page: Page,
  context: BrowserContext,
  options: { logout?: FakeResponse } = {},
): Promise<void> {
  await applyFakeSessionCookies(context, requireBaseUrl());
  await installFakeBackend(page, {
    logout: options.logout,
  });
  await page.goto("/account");
  await expect(page.getByRole("heading", { level: 1, name: "Minha conta" })).toBeVisible({
    timeout: 20_000,
  });
}

test.describe("account", () => {
  test("shows the real profile and honest states for the unsupported sections", async ({
    page,
    context,
  }) => {
    await openAccount(page, context);

    await expect(page.getByText("06 / Conta")).toBeVisible();
    await expect(page.getByRole("tab", { name: "Perfil" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    const profilePanel = page.getByRole("tabpanel", { name: "Perfil" });
    await expect(profilePanel.getByText(FAKE_USER.name)).toBeVisible();
    await expect(profilePanel.getByText(FAKE_USER.email).first()).toBeVisible();
    await expect(profilePanel.getByLabel("Nome de exibição")).not.toBeEditable();
    await expect(profilePanel.getByLabel("E-mail", { exact: true })).not.toBeEditable();
    await expect(
      profilePanel.getByText("A API ainda não permite editar o nome de exibição."),
    ).toBeVisible();

    await page.getByRole("tab", { name: "Perfil" }).focus();
    await page.keyboard.press("ArrowDown");
    await expect(page.getByRole("tab", { name: "Organização" })).toBeFocused();
    const organizationPanel = page.getByRole("tabpanel", { name: "Organização" });
    await expect(
      organizationPanel.getByText(
        "A API atual é individual e ainda não expõe organização, plano ou membros.",
      ),
    ).toBeVisible();
    await expect(organizationPanel.getByText("Não disponível")).toHaveCount(3);
    await expect(organizationPanel.getByText("Usuário")).toBeVisible();

    await page.getByRole("tab", { name: "Notificações" }).click();
    const notificationsPanel = page.getByRole("tabpanel", { name: "Notificações" });
    await expect(
      notificationsPanel.getByRole("link", { name: "Gerenciar canais" }),
    ).toHaveAttribute("href", "/notificacoes#canais");
    await expect(
      notificationsPanel.getByRole("link", { name: "Abrir central de notificações" }),
    ).toHaveAttribute("href", "/notificacoes");

    await page.getByRole("tab", { name: "Segurança e sessões" }).click();
    const securityPanel = page.getByRole("tabpanel", { name: "Segurança e sessões" });
    await expect(securityPanel.getByText("Google").first()).toBeVisible();
    await expect(securityPanel.getByText(/Expira em/)).toBeVisible();
    await expect(securityPanel.getByText("Início da sessão não informado pela API.")).toBeVisible();
    await expect(
      securityPanel.getByRole("button", { name: "Sair de todos os dispositivos" }),
    ).toBeDisabled();
    await expect(
      securityPanel.getByRole("button", { name: "Sair deste dispositivo" }),
    ).toBeEnabled();

    await page.getByRole("tab", { name: "Privacidade e dados" }).click();
    const privacyPanel = page.getByRole("tabpanel", { name: "Privacidade e dados" });
    await expect(privacyPanel.getByText("Documentos armazenados", { exact: true })).toBeVisible();
    await expect(privacyPanel.getByText("Uso de armazenamento", { exact: true })).toBeVisible();
    await expect(privacyPanel.getByText("Não informado pela API")).toHaveCount(2);
    await expect(
      privacyPanel.getByRole("link", { name: "Abrir canal de privacidade" }).first(),
    ).toHaveAttribute("href", "https://privacy.sentinelpay.test/contato");
    await expect(
      privacyPanel.getByText("Enviar e-mail para privacidade@sentinelpay.test"),
    ).toBeVisible();

    await page.getByRole("tab", { name: "Zona de perigo" }).click();
    const dangerPanel = page.getByRole("tabpanel", { name: "Zona de perigo" });
    await expect(
      dangerPanel.getByRole("button", { name: "Solicitar exclusão da conta" }),
    ).toBeVisible();
    await expect(
      dangerPanel.getByText(
        "A API ainda não permite excluir a conta automaticamente. A solicitação é encaminhada pelo canal de privacidade.",
      ),
    ).toBeVisible();
  });

  test("applies and persists language, theme and date format", async ({ page, context }) => {
    await openAccount(page, context);
    await page.getByRole("tab", { name: "Preferências" }).click();

    await page.getByRole("combobox", { name: "Idioma" }).click();
    await page.getByRole("option", { name: "Inglês" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "My account" })).toBeVisible({
      timeout: 20_000,
    });

    await page.getByRole("tab", { name: "Preferences" }).click();
    await page.getByRole("combobox", { name: "Theme" }).click();
    await page.getByRole("option", { name: "Dark" }).click();
    await expect
      .poll(() => page.evaluate(() => document.documentElement.dataset.theme))
      .toBe("dark");

    await page.getByRole("combobox", { name: "Date format" }).click();
    await page.getByRole("option", { name: "DD/MM/YYYY" }).click();
    await expect(page.getByText("Example: 16/11/2026")).toBeVisible();

    const cookies = await context.cookies(requireBaseUrl());
    expect(cookies.find((cookie) => cookie.name === "locale")?.value).toBe("en");
    expect(cookies.find((cookie) => cookie.name === "theme")?.value).toBe("dark");
    expect(cookies.find((cookie) => cookie.name === "date_format")?.value).toBe("dmy");

    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: "My account" })).toBeVisible({
      timeout: 20_000,
    });
    await page.getByRole("tab", { name: "Preferences" }).click();
    await expect(page.getByRole("combobox", { name: "Language" })).toContainText("English");
    await expect(page.getByRole("combobox", { name: "Theme" })).toContainText("Dark");
    await expect(page.getByRole("combobox", { name: "Date format" })).toContainText("DD/MM/YYYY");
    await expect(page.getByText("Example: 16/11/2026")).toBeVisible();
    await expect
      .poll(() => page.evaluate(() => document.documentElement.dataset.theme))
      .toBe("dark");
  });

  test("requires the confirmation word and never sends a destructive request", async ({
    page,
    context,
  }) => {
    await openAccount(page, context);
    await page.getByRole("tab", { name: "Zona de perigo" }).click();
    await page.getByRole("button", { name: "Solicitar exclusão da conta" }).click();

    const dialog = page.getByRole("dialog");
    const confirmation = dialog.getByLabel("Digite EXCLUIR para confirmar");
    await expect(confirmation).toBeFocused();

    await confirmation.fill("APAGAR");
    await dialog.getByRole("button", { name: "Continuar para o canal de privacidade" }).click();
    await expect(dialog.getByText("A palavra não confere. Digite EXCLUIR.")).toBeVisible();

    const destructiveRequests: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "DELETE") {
        destructiveRequests.push(request.url());
      }
    });

    await confirmation.fill("EXCLUIR");
    await dialog.getByRole("button", { name: "Continuar para o canal de privacidade" }).click();
    await expect(dialog.getByText("Nada foi excluído ainda.")).toBeVisible();
    await expect(dialog.getByRole("link", { name: "Abrir canal de privacidade" })).toHaveAttribute(
      "href",
      "https://privacy.sentinelpay.test/contato",
    );
    expect(destructiveRequests).toEqual([]);

    await dialog.getByRole("button", { name: "Fechar" }).first().click();
    await expect(page.getByRole("button", { name: "Solicitar exclusão da conta" })).toBeFocused();
  });

  test("signs out of the current device", async ({ page, context }) => {
    await openAccount(page, context, {
      logout: {
        status: 204,
        body: null,
        headers: { "set-cookie": "sp_session=; Path=/; Max-Age=0; SameSite=Lax" },
      },
    });
    await page.getByRole("tab", { name: "Segurança e sessões" }).click();

    const logoutRequest = page.waitForRequest("**/api/v1/auth/logout");
    await page.getByRole("button", { name: "Sair deste dispositivo" }).click();
    await logoutRequest;
    await expect(page).toHaveURL(/\/login/, { timeout: 20_000 });

    const cookies = await context.cookies(requireBaseUrl());
    expect(cookies.find((cookie) => cookie.name === "sp_session")).toBeUndefined();
  });

  test("has no axe violations and stays usable on mobile", async ({ page, context }) => {
    await openAccount(page, context);

    const profileResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(profileResults.violations).toEqual([]);

    await page.getByRole("tab", { name: "Preferências" }).click();
    const preferencesResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(preferencesResults.violations).toEqual([]);

    await page.setViewportSize({ width: 390, height: 900 });
    const tablist = page.getByRole("tablist", { name: "Seções da conta" });
    await expect(tablist).toBeVisible();
    await page.getByRole("tab", { name: "Zona de perigo" }).click();
    await expect(page.getByRole("button", { name: "Solicitar exclusão da conta" })).toBeVisible();

    const hasHorizontalScroll = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(hasHorizontalScroll).toBe(false);
  });
});
