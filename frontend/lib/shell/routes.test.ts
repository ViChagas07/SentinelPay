import { describe, expect, it } from "vitest";

import { SHELL_NAV_ITEMS, getShellPage, isShellPathActive } from "./routes";

describe("shell routes", () => {
  it("keeps the navigation order requested by the shell", () => {
    expect(SHELL_NAV_ITEMS.map((item) => item.href)).toEqual([
      "/painel",
      "/pagamentos",
      "/verificacao",
      "/inteligencia",
      "/folha",
      "/boletos",
      "/notificacoes",
    ]);
  });

  it("matches exact and nested paths", () => {
    expect(isShellPathActive("/painel", "/painel")).toBe(true);
    expect(isShellPathActive("/verificacao/nova", "/verificacao")).toBe(true);
    expect(isShellPathActive("/boletos", "/folha")).toBe(false);
    expect(isShellPathActive("/painelizado", "/painel")).toBe(false);
  });

  it("returns the page title and breadcrumbs for detail routes", () => {
    expect(getShellPage("/verificacao/nova").titleKey).toBe("shell.action.newVerification");
    expect(getShellPage("/verificacao/nova").breadcrumbs.map((item) => item.labelKey)).toEqual([
      "shell.nav.painel",
      "shell.nav.verificacao",
      "shell.action.newVerification",
    ]);

    expect(getShellPage("/account").titleKey).toBe("shell.nav.account");
    expect(getShellPage("/account").breadcrumbs).toHaveLength(2);
  });

  it("returns no breadcrumbs for top level routes", () => {
    expect(getShellPage("/painel").breadcrumbs).toEqual([]);
    expect(getShellPage("/notificacoes").breadcrumbs).toEqual([]);
  });

  it("falls back to the app title for unknown routes", () => {
    expect(getShellPage("/desconhecido").titleKey).toBe("meta.title");
  });
});
