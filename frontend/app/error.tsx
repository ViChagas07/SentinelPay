"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Logo } from "@/components/brand/logo";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/provider";
import { reportBoundaryError } from "@/lib/observability/sentry";

type ErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  const { t } = useI18n();

  useEffect(() => {
    reportBoundaryError(error, "app");
  }, [error]);

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main
        id="conteudo"
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-5 py-24 sm:px-8"
      >
        <Logo className="mb-6 size-10" title={t("app.name")} />
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-muted-foreground tabular-nums">
          500
        </p>
        <h1 className="mt-4 font-serif text-5xl tracking-tight sm:text-6xl">{t("error.title")}</h1>
        <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground">
          {t("error.description")}
        </p>
        {error.digest ? (
          <p className="mt-4 font-mono text-xs text-muted-foreground tabular-nums">
            {error.digest}
          </p>
        ) : null}
        <div className="mt-8 flex flex-wrap gap-3">
          <Button onClick={reset}>{t("common.retry")}</Button>
          <Button asChild variant="outline">
            <Link href="/">{t("common.backHome")}</Link>
          </Button>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
