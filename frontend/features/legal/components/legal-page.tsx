"use client";

import Link from "next/link";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { PageTransition } from "@/components/ui/motion/page-transition";
import { Eyebrow } from "@/components/ui/eyebrow";
import { useI18n } from "@/lib/i18n/provider";

export function LegalPage({ kind }: Readonly<{ kind: "terms" | "privacy" }>) {
  const { t } = useI18n();
  const isTerms = kind === "terms";

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main id="conteudo" className="flex-1">
        <PageTransition className="mx-auto w-full max-w-3xl px-5 py-16 sm:px-8">
          <Eyebrow number={isTerms ? "01" : "02"} label={t("nav.label")} />
          <h1 className="mt-4 font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
            {t(isTerms ? "terms.title" : "privacy.title")}
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            {t(isTerms ? "terms.description" : "privacy.description")}
          </p>
          <div className="mt-8 space-y-4 border-t border-border pt-6 text-sm leading-relaxed text-muted-foreground">
            <p>{t(isTerms ? "terms.body" : "privacy.body")}</p>
            <p>{t(isTerms ? "terms.dataBody" : "privacy.rightsBody")}</p>
          </div>
          <div className="mt-10">
            <Link
              href="/"
              className="text-sm text-foreground underline underline-offset-4 hover:no-underline"
            >
              {t("common.backHome")}
            </Link>
          </div>
        </PageTransition>
      </main>
      <SiteFooter />
    </div>
  );
}
