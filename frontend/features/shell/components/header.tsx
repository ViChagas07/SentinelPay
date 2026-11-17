"use client";

import { Menu, Search } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { LanguageSelector } from "@/components/language-selector";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import type { UserProfile } from "@/lib/api/schemas";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import type { ShellBreadcrumb } from "@/lib/shell/routes";

import { Breadcrumbs } from "./breadcrumbs";
import { UserMenu } from "./user-menu";

export type ShellHeaderProps = {
  titleKey: TranslationKey;
  breadcrumbs: readonly ShellBreadcrumb[];
  user: UserProfile;
  onOpenMenu: () => void;
  onOpenSearch: () => void;
  onLogout: () => void;
  loggingOut: boolean;
};

export function ShellHeader({
  titleKey,
  breadcrumbs,
  user,
  onOpenMenu,
  onOpenSearch,
  onLogout,
  loggingOut,
}: ShellHeaderProps) {
  const { t } = useI18n();

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background">
      <div className="flex h-16 min-w-0 items-center gap-2 px-3 sm:gap-3 sm:px-6">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="shrink-0 lg:hidden"
          aria-label={t("shell.header.openMenu")}
          onClick={onOpenMenu}
        >
          <Menu aria-hidden="true" />
        </Button>

        <Link
          href="/painel"
          aria-label={t("app.name")}
          className="shrink-0 rounded-[6px] lg:hidden"
        >
          <Logo className="h-7 w-auto" title={t("app.name")} sizes="28px" />
        </Link>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{t(titleKey)}</p>
          <div className="hidden sm:block">
            <Breadcrumbs items={breadcrumbs} />
          </div>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={onOpenSearch}
        >
          <Search aria-hidden="true" />
          <span className="sr-only">{t("shell.header.search")}</span>
          <span aria-hidden="true" className="hidden md:inline">
            {t("shell.header.search")}
          </span>
          <kbd
            aria-hidden="true"
            className="hidden rounded-[4px] border border-border px-1.5 py-0.5 font-mono text-[0.6rem] text-muted-foreground lg:inline"
          >
            {t("shell.command.shortcut")}
          </kbd>
        </Button>

        <div className="hidden items-center gap-2 sm:flex">
          <ThemeToggle />
          <LanguageSelector />
        </div>

        <UserMenu user={user} variant="header" onLogout={onLogout} loggingOut={loggingOut} />
      </div>
    </header>
  );
}
