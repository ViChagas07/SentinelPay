import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { installAuthBackend } from "./support/auth-backend";

test.describe("password sign in", () => {
  test("signs in and reaches the app home", async ({ page }) => {
    await installAuthBackend(page);
    await page.goto("/login");

    await page.getByRole("checkbox").check();
    await page.getByLabel("E-mail").fill("pessoa@example.com");
    await page.getByLabel("Senha", { exact: true }).fill("frase secreta longa");
    await page.getByRole("button", { name: /^Entrar$/ }).click();

    await expect(page).toHaveURL(/\/painel/, { timeout: 20_000 });
  });

  test("shows a generic error for wrong credentials", async ({ page }) => {
    await installAuthBackend(page, {
      login: () => ({
        status: 401,
        body: { code: "invalid_credentials", title: "Unauthorized", status: 401 },
      }),
    });
    await page.goto("/login");

    await page.getByRole("checkbox").check();
    await page.getByLabel("E-mail").fill("pessoa@example.com");
    await page.getByLabel("Senha", { exact: true }).fill("senha errada longa");
    await page.getByRole("button", { name: /^Entrar$/ }).click();

    await expect(page.getByRole("alert").filter({ hasText: /incorretos/i })).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("sends an unverified account to the confirmation screen", async ({ page }) => {
    await installAuthBackend(page, {
      login: () => ({
        status: 403,
        body: { code: "email_not_verified", title: "Forbidden", status: 403 },
      }),
    });
    await page.goto("/login");

    await page.getByRole("checkbox").check();
    await page.getByLabel("E-mail").fill("pessoa@example.com");
    await page.getByLabel("Senha", { exact: true }).fill("frase secreta longa");
    await page.getByRole("button", { name: /^Entrar$/ }).click();

    await expect(page).toHaveURL(/\/confirmar-email/, { timeout: 20_000 });
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/Confirme seu e-mail/);
  });

  test("shows the block message with the wait time", async ({ page }) => {
    await installAuthBackend(page, {
      login: () => ({
        status: 429,
        body: { code: "too_many_attempts", title: "Too many requests", status: 429 },
        retryAfter: "90",
      }),
    });
    await page.goto("/login");

    await page.getByRole("checkbox").check();
    await page.getByLabel("E-mail").fill("pessoa@example.com");
    await page.getByLabel("Senha", { exact: true }).fill("frase secreta longa");
    await page.getByRole("button", { name: /^Entrar$/ }).click();

    const alert = page.getByRole("alert").filter({ hasText: /Muitas tentativas/i });
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(/90/);
  });
});

test.describe("password sign up", () => {
  test("registers and lands on the confirmation screen", async ({ page }) => {
    await installAuthBackend(page);
    await page.goto("/login?modo=cadastro");

    await page.getByRole("checkbox").check();
    await page.getByLabel("Nome completo").fill("Pessoa Exemplo");
    await page.getByLabel("E-mail").fill("pessoa@example.com");
    await page.getByLabel("Senha", { exact: true }).fill("frase secreta longa");
    await page.getByLabel("Confirmar senha").fill("frase secreta longa");
    await page.getByRole("button", { name: /^Criar conta$/ }).click();

    await expect(page).toHaveURL(/\/confirmar-email\?email=/, { timeout: 20_000 });
    await expect(page.getByLabel("E-mail da conta")).toHaveValue("pessoa@example.com");
  });

  test("resends the confirmation e-mail with a cooldown", async ({ page }) => {
    await installAuthBackend(page);
    await page.goto("/confirmar-email?email=pessoa@example.com");

    await page.getByRole("button", { name: "Reenviar e-mail" }).click();

    await expect(page.getByRole("status")).toContainText(/enviamos um novo e-mail/i);
    await expect(page.getByRole("button", { name: /Aguarde/ })).toBeDisabled();
  });
});

test.describe("email verification", () => {
  test("confirms the token and clears it from the URL", async ({ page }) => {
    await installAuthBackend(page, { verify: () => ({ status: 204, body: null }) });
    await page.goto("/verificar-email?token=token-valido-de-teste-123");

    await expect(page.getByRole("heading", { level: 1 })).toContainText(/Confirme seu e-mail/);
    await expect(page.getByText(/E-mail confirmado/)).toBeVisible({ timeout: 20_000 });
    await expect(page).not.toHaveURL(/token=/);
  });

  test("explains an invalid or expired token", async ({ page }) => {
    await installAuthBackend(page, {
      verify: () => ({
        status: 400,
        body: { code: "invalid_auth_token", title: "Bad request", status: 400 },
      }),
    });
    await page.goto("/verificar-email?token=token-expirado-de-teste");

    await expect(
      page.getByRole("main").getByRole("alert").filter({ hasText: /inválido ou já expirou/i }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole("link", { name: /Reenviar o link/ })).toBeVisible();
  });
});

test.describe("password recovery", () => {
  test("shows the neutral confirmation for forgot password", async ({ page }) => {
    await installAuthBackend(page);
    await page.goto("/esqueci-senha");

    await page.getByLabel("E-mail").fill("pessoa@example.com");
    await page.getByRole("button", { name: "Enviar link" }).click();

    await expect(page.getByRole("status")).toContainText(/link de redefinição/i);
  });

  test("resets the password and clears the token from the URL", async ({ page }) => {
    await installAuthBackend(page, { reset: () => ({ status: 204, body: null }) });
    await page.goto("/redefinir-senha?token=token-de-redefinicao-123");

    await page.getByLabel("Senha", { exact: true }).fill("nova frase bem longa");
    await page.getByLabel("Confirmar senha").fill("nova frase bem longa");
    await page.getByRole("button", { name: "Salvar nova senha" }).click();

    await expect(page.getByRole("status")).toContainText(/Todas as sessões/i, {
      timeout: 20_000,
    });
    await expect(page).not.toHaveURL(/token=/);
  });

  test("blocks a weak password with the server policy", async ({ page }) => {
    await installAuthBackend(page);
    await page.goto("/redefinir-senha?token=token-de-redefinicao-123");

    await page.getByLabel("Senha", { exact: true }).fill("curta");
    await page.getByLabel("Confirmar senha").fill("curta");
    await page.getByRole("button", { name: "Salvar nova senha" }).click();

    await expect(page.getByText(/não atende aos requisitos/i)).toBeVisible();
  });
});

for (const theme of ["light", "dark"] as const) {
  test(`auth screens have no axe violations (${theme})`, async ({ page, context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    await context.addCookies([{ name: "theme", value: theme, url: baseURL }]);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await installAuthBackend(page);

    for (const path of [
      "/login",
      "/login?modo=cadastro",
      "/esqueci-senha",
      "/redefinir-senha?token=token-de-redefinicao-123",
      "/confirmar-email?email=pessoa@example.com",
    ]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations, path).toEqual([]);
    }
  });
}
