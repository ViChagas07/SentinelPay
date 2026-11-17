"use client";

import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { useI18n } from "@/lib/i18n/provider";

export function ShellFooter() {
  const { t } = useI18n();

  return (
    <footer className="border-t border-border px-4 py-3 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Logo className="size-5 opacity-80" sizes="20px" />
          <p>{t("shell.footer.note")}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/termos" className="hover:text-foreground">
            {t("shell.footer.terms")}
          </Link>
          <Link href="/privacidade" className="hover:text-foreground">
            {t("shell.footer.privacy")}
          </Link>
        </div>
      </div>
    </footer>
  );
}
