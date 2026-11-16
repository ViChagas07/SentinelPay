"use client";

import Link from "next/link";

import { LanguageSelector } from "@/components/language-selector";
import { useI18n } from "@/lib/i18n/provider";
import { resolveSupportHref } from "@/lib/site/config";

export function SiteFooter() {
  const { t } = useI18n();
  const supportHref = resolveSupportHref(process.env.NEXT_PUBLIC_SUPPORT_URL);
  const supportIsExternal = supportHref.startsWith("http");

  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <p className="font-mono text-xs tabular-nums">
          {t("landing.footer.copyright", { year: new Date().getFullYear() })}
        </p>

        <nav
          aria-label={t("landing.footer.nav")}
          className="flex flex-wrap items-center gap-x-4 gap-y-2"
        >
          <Link href="/termos" className="transition-colors hover:text-foreground">
            {t("landing.footer.terms")}
          </Link>
          <Link href="/privacidade" className="transition-colors hover:text-foreground">
            {t("landing.footer.privacy")}
          </Link>
          {supportIsExternal ? (
            <a
              href={supportHref}
              target="_blank"
              rel="noreferrer"
              className="transition-colors hover:text-foreground"
            >
              {t("landing.footer.support")}
            </a>
          ) : (
            <Link href={supportHref} className="transition-colors hover:text-foreground">
              {t("landing.footer.support")}
            </Link>
          )}
          <LanguageSelector />
        </nav>
      </div>
    </footer>
  );
}
