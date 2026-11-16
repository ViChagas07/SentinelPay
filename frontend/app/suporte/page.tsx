import type { Metadata } from "next";
import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { getServerLocale, serverTranslate } from "@/lib/i18n/server";
import { getSupportExternalUrl } from "@/lib/site/config";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();

  return {
    title: serverTranslate(locale, "support.title"),
    description: serverTranslate(locale, "support.description"),
    robots: { index: false, follow: true },
  };
}

export default async function SupportPage() {
  const locale = await getServerLocale();
  const externalUrl = getSupportExternalUrl(process.env.NEXT_PUBLIC_SUPPORT_URL);

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main id="conteudo" className="mx-auto w-full max-w-3xl flex-1 px-5 py-16 sm:px-8">
        <Eyebrow number="01" label={serverTranslate(locale, "support.eyebrow")} />
        <h1 className="mt-4 font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
          {serverTranslate(locale, "support.title")}
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          {serverTranslate(locale, "support.description")}
        </p>

        <div className="mt-8 space-y-4 border-t border-border pt-6">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {serverTranslate(locale, "support.body")}
          </p>
          {externalUrl ? (
            <Button asChild>
              <a href={externalUrl} target="_blank" rel="noreferrer">
                {serverTranslate(locale, "support.externalCta")}
                <ArrowRight aria-hidden="true" />
              </a>
            </Button>
          ) : (
            <p className="rounded-[6px] border border-border bg-surface-elevated p-4 text-sm leading-relaxed text-muted-foreground">
              {serverTranslate(locale, "support.empty")}
            </p>
          )}
        </div>

        <div className="mt-10">
          <Link
            href="/"
            className="text-sm text-foreground underline underline-offset-4 hover:no-underline"
          >
            {serverTranslate(locale, "support.back")}
          </Link>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
