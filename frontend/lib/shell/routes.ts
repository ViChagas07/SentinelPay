import type { TranslationKey } from "@/lib/i18n";

export type ShellNavItem = {
  href: string;
  labelKey: TranslationKey;
};

export const SHELL_NAV_ITEMS: readonly ShellNavItem[] = [
  { href: "/painel", labelKey: "shell.nav.painel" },
  { href: "/pagamentos", labelKey: "shell.nav.pagamentos" },
  { href: "/verificacao", labelKey: "shell.nav.verificacao" },
  { href: "/inteligencia", labelKey: "shell.nav.inteligencia" },
  { href: "/folha", labelKey: "shell.nav.folha" },
  { href: "/boletos", labelKey: "shell.nav.boletos" },
  { href: "/notificacoes", labelKey: "shell.nav.notificacoes" },
];

export type ShellBreadcrumb = {
  labelKey: TranslationKey;
  href?: string;
};

export type ShellPage = {
  titleKey: TranslationKey;
  breadcrumbs: readonly ShellBreadcrumb[];
};

const PANEL_CRUMB: ShellBreadcrumb = {
  labelKey: "shell.nav.painel",
  href: "/painel",
};

const PAGE_RULES: readonly (ShellPage & { href: string })[] = [
  {
    href: "/verificacao/nova",
    titleKey: "shell.action.newVerification",
    breadcrumbs: [
      PANEL_CRUMB,
      { labelKey: "shell.nav.verificacao", href: "/verificacao" },
      { labelKey: "shell.action.newVerification" },
    ],
  },
  {
    href: "/account",
    titleKey: "shell.nav.account",
    breadcrumbs: [PANEL_CRUMB, { labelKey: "shell.nav.account" }],
  },
  { href: "/painel", titleKey: "shell.nav.painel", breadcrumbs: [] },
  { href: "/pagamentos", titleKey: "shell.nav.pagamentos", breadcrumbs: [] },
  { href: "/verificacao", titleKey: "shell.nav.verificacao", breadcrumbs: [] },
  { href: "/inteligencia", titleKey: "shell.nav.inteligencia", breadcrumbs: [] },
  { href: "/folha", titleKey: "shell.nav.folha", breadcrumbs: [] },
  { href: "/boletos", titleKey: "shell.nav.boletos", breadcrumbs: [] },
  { href: "/notificacoes", titleKey: "shell.nav.notificacoes", breadcrumbs: [] },
];

export function isShellPathActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function getShellPage(pathname: string): ShellPage {
  const match = PAGE_RULES.find((rule) => isShellPathActive(pathname, rule.href));

  if (!match) {
    return { titleKey: "meta.title", breadcrumbs: [] };
  }

  return { titleKey: match.titleKey, breadcrumbs: match.breadcrumbs };
}
