"use client";

import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";

export default function NotFound() {
  const { t } = useI18n();

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main
        id="conteudo"
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-5 py-24 sm:px-8"
      >
        <Logo className="mb-6 size-10" title={t("app.name")} />
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-muted-foreground tabular-nums">
          404
        </p>
        <h1 className="mt-4 font-serif text-5xl tracking-tight sm:text-6xl">
          {t("notFound.title")}
        </h1>
        <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground">
          {t("notFound.description")}
        </p>
        <div className="mt-8">
          <Button asChild>
            <Link href="/">{t("common.backHome")}</Link>
          </Button>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
