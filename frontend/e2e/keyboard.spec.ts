import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { applyFakeSessionCookies, installFakeBackend } from "./support/fake-backend";

const ROUTES = [
  { path: "/", session: false },
  { path: "/login", session: false },
  { path: "/termos", session: false },
  { path: "/privacidade", session: false },
  { path: "/suporte", session: false },
  { path: "/servico-indisponivel", session: false },
  { path: "/painel", session: true },
  { path: "/verificacao", session: true },
  { path: "/verificacao/nova", session: true },
  { path: "/verificacao/22222222-2222-4222-8222-222222222222", session: true },
  { path: "/boletos", session: true },
  { path: "/folha", session: true },
  { path: "/pagamentos", session: true },
  { path: "/notificacoes", session: true },
  { path: "/account", session: true },
  { path: "/inteligencia", session: true },
] as const;

type FocusInfo = {
  tag: string;
  role: string | null;
  text: string;
  outlineStyle: string;
  outlineWidth: string;
  boxShadow: string;
};

function requireBaseUrl(): string {
  const baseURL = test.info().project.use.baseURL;

  if (!baseURL) {
    throw new Error("Playwright baseURL is not configured");
  }

  return baseURL;
}

async function prepare(page: Page, context: BrowserContext, session: boolean): Promise<void> {
  const baseURL = requireBaseUrl();
  await context.clearCookies();

  if (session) {
    await applyFakeSessionCookies(context, baseURL);
  }

  await installFakeBackend(page, {
    list: { status: 200, body: { items: [], next_cursor: null } },
    payables: { status: 200, body: { items: [], next_cursor: null } },
    notifications: { status: 200, body: { items: [], next_cursor: null } },
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
}

async function focusedInfo(page: Page): Promise<FocusInfo | null> {
  return page.evaluate(() => {
    const element = document.activeElement;

    if (!element || element === document.body || element === document.documentElement) {
      return null;
    }

    const style = window.getComputedStyle(element);

    return {
      tag: element.tagName.toLowerCase(),
      role: element.getAttribute("role"),
      text: (element.textContent ?? "").trim().slice(0, 80),
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
      boxShadow: style.boxShadow,
    };
  });
}

function hasVisibleFocus(info: FocusInfo): boolean {
  const hasOutline = info.outlineStyle !== "none" && info.outlineWidth !== "0px";
  return hasOutline || (info.boxShadow !== "none" && info.boxShadow.length > 0);
}

function isInteractive(info: FocusInfo): boolean {
  return (
    ["a", "button", "input", "select", "textarea", "summary"].includes(info.tag) ||
    info.role === "tab" ||
    info.role === "menuitem" ||
    info.role === "option" ||
    info.role === "switch"
  );
}

for (const route of ROUTES) {
  test(`teclado: ${route.path}`, async ({ page, context }) => {
    await prepare(page, context, route.session);
    await page.goto(route.path);
    await expect(page.locator("main#conteudo, main").first()).toBeVisible({ timeout: 30_000 });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(300);

    await page.keyboard.press("Tab");
    const skipLink = await focusedInfo(page);
    expect(skipLink, `${route.path}: primeiro Tab nao encontrou foco`).not.toBeNull();
    expect(skipLink?.tag).toBe("a");
    expect(skipLink?.text.length).toBeGreaterThan(0);

    const seen = new Set<string>();

    for (let index = 0; index < 14; index += 1) {
      await page.keyboard.press("Tab");
      const info = await focusedInfo(page);

      if (!info) {
        continue;
      }

      const key = `${info.tag}:${info.role ?? ""}:${info.text}`;

      if (seen.has(key)) {
        break;
      }

      seen.add(key);
      expect(
        isInteractive(info),
        `${route.path}: foco em elemento nao interativo (${info.tag}, ${info.role ?? "sem role"})`,
      ).toBe(true);
      expect(
        hasVisibleFocus(info),
        `${route.path}: foco sem indicador visivel em ${info.tag} "${info.text}"`,
      ).toBe(true);
    }

    expect(seen.size, `${route.path}: poucos elementos alcancaveis por teclado`).toBeGreaterThan(4);
  });
}
