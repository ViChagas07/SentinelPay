"use client";

import Link from "next/link";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n/provider";

export default function ServiceUnavailablePage() {
  const { t } = useI18n();

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main
        id="conteudo"
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-5 py-24 sm:px-8"
      >
        <p className="inline-flex w-fit items-center gap-2 rounded-[6px] border border-border bg-surface px-3 py-1 font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          <span className="size-1.5 rounded-full bg-primary" aria-hidden="true" />
          {t("unavailable.eyebrow")}
        </p>
        <h1 className="mt-6 font-serif text-5xl tracking-tight sm:text-6xl">
          {t("unavailable.title")}
        </h1>
        <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground">
          {t("unavailable.description")}
        </p>
        <Card className="mt-8">
          <CardHeader>
            <h2 className="text-lg font-semibold tracking-tight">{t("unavailable.eyebrow")}</h2>
            <CardDescription>{t("unavailable.note")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Button onClick={() => window.location.reload()}>{t("unavailable.retry")}</Button>
            <Button asChild variant="outline">
              <Link href="/">{t("common.backHome")}</Link>
            </Button>
          </CardContent>
        </Card>
      </main>
      <SiteFooter />
    </div>
  );
}
