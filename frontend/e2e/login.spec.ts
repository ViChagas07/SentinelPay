import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const THEMES = ["light", "dark"] as const;

for (const theme of THEMES) {
  test(`login has no axe violations (${theme})`, async ({ page, context }) => {
    const baseURL = test.info().project.use.baseURL;

    if (!baseURL) {
      throw new Error("Playwright baseURL is not configured");
    }

    await context.addCookies([{ name: "theme", value: theme, url: baseURL }]);
    await page.emulateMedia({ reducedMotion: "reduce" });

    for (const path of ["/login", "/login?modo=cadastro"]) {
      await page.goto(path);
      await expect(page.getByRole("button", { name: /Google/ })).toBeVisible();

      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations, `${path}`).toEqual([]);
    }
  });
}

test("login logo leads to the public home", async ({ page }) => {
  await page.goto("/login");
  await expect(page.locator("aside").getByRole("link", { name: "SentinelPay" })).toHaveAttribute(
    "href",
    "/",
  );
});

test("login shows the form heading without repeating the panel title", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { level: 1, name: /cada sinal/i })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /Bem-vindo de volta/i })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: /cada sinal/i })).toHaveCount(0);
});

test("login requires the terms before starting Google sign-in", async ({ page }) => {
  await page.goto("/login");

  const google = page.getByRole("button", { name: /Continuar com Google/ });
  await google.click();

  const alert = page.locator("form p[role='alert']");
  await expect(alert).toContainText(/aceite/i);
  await expect(page.getByRole("checkbox")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByRole("checkbox")).toBeFocused();
  await expect(page).toHaveURL(/\/login/);

  await page.getByRole("checkbox").check();
  await expect(alert).toHaveCount(0);
  await expect(page.getByRole("checkbox")).not.toHaveAttribute("aria-invalid", "true");
});

test("login tabs switch with the URL and keep the terms acceptance", async ({ page }) => {
  await page.goto("/login");

  const signin = page.getByRole("tab", { name: "Entrar" });
  const signup = page.getByRole("tab", { name: "Criar conta" });
  await expect(signin).toHaveAttribute("aria-selected", "true");

  await page.getByRole("checkbox").check();
  await signup.click();

  await expect(page).toHaveURL(/modo=cadastro/);
  await expect(signup).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { level: 2, name: "Crie sua conta" })).toBeVisible();
  await expect(page.getByRole("checkbox")).toBeChecked();
  await expect(page.getByRole("button", { name: /Cadastrar com Google/ })).toBeEnabled();

  await page.getByRole("button", { name: "Entrar", exact: true }).last().click();
  await expect(page).not.toHaveURL(/modo=cadastro/);
  await expect(signin).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { level: 2, name: "Bem-vindo de volta" })).toBeVisible();
});

test("login tabs respond to the arrow keys", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("tab", { name: "Entrar" }).focus();
  await page.keyboard.press("ArrowRight");

  await expect(page.getByRole("tab", { name: "Criar conta" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page).toHaveURL(/modo=cadastro/);
});

test("login renders the password form when the backend enables it", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByLabel("E-mail")).toBeVisible();
  await expect(page.getByLabel("Senha", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Esqueceu a senha?" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Entrar$/ })).toBeVisible();

  await page.goto("/login?modo=cadastro");
  await expect(page.getByLabel("Nome completo")).toBeVisible();
  await expect(page.getByLabel("Confirmar senha")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Criar conta$/ })).toBeVisible();
});

test("sign-up validates the password confirmation and the policy", async ({ page }) => {
  await page.goto("/login?modo=cadastro");

  const password = page.getByLabel("Senha", { exact: true });
  const confirm = page.getByLabel("Confirmar senha");

  await password.fill("frase secreta longa");
  await confirm.fill("outra frase longa");
  await expect(page.getByText("As senhas não coincidem.")).toBeVisible();

  await confirm.fill("frase secreta longa");
  await expect(page.getByText("As senhas não coincidem.")).toHaveCount(0);

  await password.fill("123");
  await password.blur();
  await expect(page.getByText("A senha não atende aos requisitos.")).toBeVisible();
});

test("sign-up requires the terms before submitting", async ({ page }) => {
  await page.goto("/login?modo=cadastro");

  await page.getByLabel("Nome completo").fill("Pessoa Exemplo");
  await page.getByLabel("E-mail").fill("pessoa@example.com");
  await page.getByLabel("Senha", { exact: true }).fill("frase secreta longa");
  await page.getByLabel("Confirmar senha").fill("frase secreta longa");

  const submit = page.getByRole("button", { name: /^Criar conta$/ });
  await submit.click();
  await expect(page.locator("form p[role='alert']")).toContainText(/aceite/i);
  await expect(page).toHaveURL(/login/);

  await page.getByRole("checkbox").check();
  await expect(page.locator("form p[role='alert']")).toHaveCount(0);
});

test("login back button leaves the login page", async ({ page }) => {
  await page.goto("/");
  await page.goto("/login");
  await expect(page).toHaveURL(/\/login/);

  await page
    .getByRole("button", { name: /^Voltar$/ })
    .first()
    .click();
  await expect(page).toHaveURL(/\/$/);
});

test("login error notice is announced", async ({ page }) => {
  await page.goto("/login?reason=auth_failed&code=email_not_verified");
  await expect(page.getByRole("heading", { level: 2 })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: /não está verificado/i })).toContainText(
    /não está verificado/i,
    {
      timeout: 10_000,
    },
  );
});

test("expired session notice is shown", async ({ page }) => {
  await page.goto("/login?reason=expired");
  await expect(page.getByRole("heading", { level: 2 })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: /expirou/i })).toContainText(/expirou/i, {
    timeout: 10_000,
  });
});

test("denied access notice is shown", async ({ page }) => {
  await page.goto("/login?reason=forbidden&code=forbidden");
  await expect(page.getByRole("heading", { level: 2 })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: /permissão/i })).toContainText(
    /permissão/i,
    {
      timeout: 10_000,
    },
  );
});

test("login keeps both tabs visible when email sign-up is unavailable", async ({ page }) => {
  const signupDisabled = await page.request
    .get("/api/v1/auth/capabilities")
    .then((response) => response.json())
    .catch(() => null);

  test.skip(
    !signupDisabled || signupDisabled.signup_enabled !== false || !signupDisabled.password_enabled,
    "backend ativo com cadastro por e-mail; o estado sem cadastro e coberto em lib/auth/login-visibility.test.ts",
  );

  await page.goto("/login");

  const signin = page.getByRole("tab", { name: "Entrar" });
  const signup = page.getByRole("tab", { name: "Criar conta" });
  await expect(signin).toBeVisible();
  await expect(signup).toBeVisible();
  await expect(signin).toHaveAttribute("aria-selected", "true");

  await signup.click();
  await expect(page).toHaveURL(/modo=cadastro/);
  await expect(page.getByRole("heading", { level: 2, name: "Crie sua conta" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Cadastrar com Google/ })).toBeVisible();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  await expect(page.getByLabel("Nome completo")).toHaveCount(0);
  await expect(page.getByLabel("Confirmar senha")).toHaveCount(0);
});
