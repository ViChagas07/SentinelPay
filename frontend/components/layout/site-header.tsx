"use client";

import { Menu } from "lucide-react";
import Link from "next/link";

import { Wordmark } from "@/components/brand/logo";
import { LanguageSelector } from "@/components/language-selector";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

const LANDING_NAV = [
  { href: "/#como-funciona", labelKey: "landing.nav.how" },
  { href: "/#recursos", labelKey: "landing.nav.features" },
  { href: "/#normas", labelKey: "landing.nav.norms" },
] as const satisfies readonly { href: string; labelKey: TranslationKey }[];

export type SiteHeaderProps = {
  sessionActive?: boolean;
};

export function SiteHeader({ sessionActive = false }: SiteHeaderProps) {
  const { t } = useI18n();
  const dashboardLabel = sessionActive ? t("landing.nav.dashboard") : t("landing.nav.enter");

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
        <Link href="/" className="rounded-[6px]" aria-label={t("app.name")}>
          <Wordmark name={t("app.name")} />
        </Link>

        <nav aria-label={t("landing.nav.primary")} className="hidden items-center gap-1 md:flex">
          {LANDING_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-[6px] px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
            >
              {t(item.labelKey)}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <LanguageSelector />
          <Button asChild size="sm" className="hidden md:inline-flex">
            <Link href="/painel">{dashboardLabel}</Link>
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className="md:hidden"
                aria-label={t("landing.nav.menu")}
              >
                <Menu aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 md:hidden">
              {LANDING_NAV.map((item) => (
                <DropdownMenuItem key={item.href} asChild>
                  <Link href={item.href}>{t(item.labelKey)}</Link>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href="/painel" className="font-medium">
                  {dashboardLabel}
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
