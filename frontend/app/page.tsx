import type { Metadata } from "next";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { cookies } from "next/headers";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import {
  FeaturePreview,
  type FeaturePreviewVariant,
} from "@/features/landing/components/feature-preview";
import { HeroDemo } from "@/features/landing/components/hero-demo";
import { HowItWorks } from "@/features/landing/components/how-it-works";
import { RiskIndex } from "@/features/landing/components/risk-index";
import { SectionHeading } from "@/features/landing/components/section-heading";
import styles from "@/features/landing/landing.module.css";
import type { Locale, TranslationKey, TranslationParams } from "@/lib/i18n";
import { getServerLocale, serverTranslate } from "@/lib/i18n/server";
import { hasSessionCookie } from "@/lib/session/cookies";
import { cn } from "@/lib/utils";

const OG_LOCALE: Record<Locale, string> = {
  pt: "pt_BR",
  es: "es_ES",
  en: "en_US",
};

const OG_ALTERNATES: Record<Locale, readonly string[]> = {
  pt: ["es_ES", "en_US"],
  es: ["pt_BR", "en_US"],
  en: ["pt_BR", "es_ES"],
};

type FeatureItem = {
  id: string;
  href: string;
  titleKey: TranslationKey;
  bodyKey: TranslationKey;
  variant: FeaturePreviewVariant;
};

const FEATURES: readonly FeatureItem[] = [
  {
    id: "painel",
    href: "/painel",
    titleKey: "landing.features.painel.title",
    bodyKey: "landing.features.painel.body",
    variant: "painel",
  },
  {
    id: "verificacao",
    href: "/verificacao",
    titleKey: "landing.features.verificacao.title",
    bodyKey: "landing.features.verificacao.body",
    variant: "verificacao",
  },
  {
    id: "boletos",
    href: "/boletos",
    titleKey: "landing.features.boletos.title",
    bodyKey: "landing.features.boletos.body",
    variant: "boletos",
  },
  {
    id: "folha",
    href: "/folha",
    titleKey: "landing.features.folha.title",
    bodyKey: "landing.features.folha.body",
    variant: "folha",
  },
  {
    id: "notificacoes",
    href: "/notificacoes",
    titleKey: "landing.features.notificacoes.title",
    bodyKey: "landing.features.notificacoes.body",
    variant: "notificacoes",
  },
  {
    id: "inteligencia",
    href: "/inteligencia",
    titleKey: "landing.features.inteligencia.title",
    bodyKey: "landing.features.inteligencia.body",
    variant: "inteligencia",
  },
  {
    id: "pagamentos",
    href: "/pagamentos",
    titleKey: "landing.features.pagamentos.title",
    bodyKey: "landing.features.pagamentos.body",
    variant: "pagamentos",
  },
];

const NORMS: readonly { titleKey: TranslationKey; bodyKey: TranslationKey }[] = [
  { titleKey: "landing.norms.febrabanTitle", bodyKey: "landing.norms.febrabanBody" },
  { titleKey: "landing.norms.inssTitle", bodyKey: "landing.norms.inssBody" },
  { titleKey: "landing.norms.workerTitle", bodyKey: "landing.norms.workerBody" },
  { titleKey: "landing.norms.knowledgeTitle", bodyKey: "landing.norms.knowledgeBody" },
];

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();
  const title = serverTranslate(locale, "landing.meta.title");
  const description = serverTranslate(locale, "landing.meta.description");

  return {
    title,
    description,
    alternates: {
      canonical: "/",
    },
    openGraph: {
      type: "website",
      url: "/",
      siteName: "SentinelPay",
      title,
      description,
      locale: OG_LOCALE[locale],
      alternateLocale: [...OG_ALTERNATES[locale]],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ["/opengraph-image"],
    },
  };
}

export default async function LandingPage() {
  const locale = await getServerLocale();
  const cookieStore = await cookies();
  const sessionActive = hasSessionCookie(cookieStore);

  const t = (key: TranslationKey, params?: TranslationParams) =>
    serverTranslate(locale, key, params);

  const dashboardLabel = sessionActive ? t("landing.nav.dashboard") : t("landing.nav.enter");

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader sessionActive={sessionActive} />
      <main id="conteudo" className="flex-1">
        <section className="border-b border-border bg-landing" aria-labelledby="hero-title">
          <div className="mx-auto grid max-w-6xl gap-12 px-5 pb-16 pt-14 sm:px-8 sm:pb-20 sm:pt-20 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:gap-16 lg:pb-24 lg:pt-24">
            <div className="min-w-0">
              <Eyebrow number="01" label={t("landing.hero.eyebrow")} />
              <h1
                id="hero-title"
                className="mt-6 max-w-2xl font-serif text-5xl leading-[0.95] tracking-tight sm:text-6xl lg:text-7xl"
              >
                {t("landing.hero.titleLead")}{" "}
                <em className={styles.accent}>{t("landing.hero.titleAccent")}</em>
              </h1>
              <p className="mt-6 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
                {t("landing.hero.description")}
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                <Button asChild size="lg">
                  <Link href="/painel">
                    {dashboardLabel}
                    <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg">
                  <a href="#como-funciona">{t("landing.hero.secondaryCta")}</a>
                </Button>
              </div>
            </div>
            <HeroDemo />
          </div>
        </section>

        <HowItWorks />

        <section
          id="recursos"
          aria-labelledby="recursos-title"
          className="scroll-mt-24 border-b border-border"
        >
          <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 sm:py-24">
            <SectionHeading
              id="recursos-title"
              number="03"
              label={t("landing.features.eyebrow")}
              title={t("landing.features.titleLead")}
              accent={t("landing.features.titleAccent")}
              description={t("landing.features.description")}
            />

            <ol className="mt-12 border-t border-border">
              {FEATURES.map((feature, index) => {
                const reversed = index % 2 === 1;

                return (
                  <li key={feature.id} className="border-b border-border">
                    <Link
                      href={feature.href}
                      className="group grid gap-8 py-10 lg:grid-cols-2 lg:items-center lg:gap-14 lg:py-14"
                    >
                      <div className={cn("min-w-0", reversed && "lg:order-2")}>
                        <div className="flex items-baseline gap-3">
                          <span className="font-mono text-xs text-muted-foreground tabular-nums">
                            0{index + 1}
                          </span>
                          <h3 className="font-serif text-3xl leading-tight tracking-tight">
                            {t(feature.titleKey)}
                          </h3>
                        </div>
                        <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
                          {t(feature.bodyKey)}
                        </p>
                        <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-foreground">
                          {t("landing.features.open")}
                          <ArrowUpRight
                            className="size-4 text-muted-foreground"
                            aria-hidden="true"
                          />
                        </span>
                      </div>
                      <div className={cn("min-w-0", reversed && "lg:order-1")}>
                        <div className="rounded-[6px] border border-border bg-surface-elevated p-3 transition-colors group-hover:border-petrol-500/50 group-hover:bg-surface">
                          <FeaturePreview variant={feature.variant} />
                          <p className="mt-2 text-center font-mono text-[0.55rem] uppercase tracking-[0.18em] text-muted-foreground">
                            {t("landing.hero.demoLabel")}
                          </p>
                        </div>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>

        <RiskIndex />

        <section
          id="normas"
          aria-labelledby="normas-title"
          className="scroll-mt-24 border-b border-border"
        >
          <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 sm:py-24">
            <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
              <div>
                <SectionHeading
                  id="normas-title"
                  number="05"
                  label={t("landing.norms.eyebrow")}
                  title={t("landing.norms.titleLead")}
                  accent={t("landing.norms.titleAccent")}
                  description={t("landing.norms.description")}
                />
                <p className="mt-6 max-w-md border-l-2 border-petrol-500/50 pl-4 text-sm leading-relaxed text-muted-foreground">
                  {t("landing.norms.disclaimer")}
                </p>
              </div>

              <div className="border-t border-border">
                {NORMS.map((norm, index) => (
                  <article
                    key={norm.titleKey}
                    className="border-b border-border py-8 first:pt-0 lg:grid lg:grid-cols-[auto_1fr] lg:gap-6"
                  >
                    <span className="font-mono text-xs text-muted-foreground tabular-nums">
                      0{index + 1}
                    </span>
                    <div className="mt-2 lg:mt-0">
                      <h3 className="font-serif text-2xl leading-tight tracking-tight">
                        {t(norm.titleKey)}
                      </h3>
                      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
                        {t(norm.bodyKey)}
                      </p>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="final-title" className="bg-petrol-800 text-on-petrol">
          <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 sm:py-24">
            <div className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
              <div>
                <p className="flex flex-wrap items-baseline gap-x-2 font-mono text-[0.65rem] uppercase tracking-[0.22em] text-on-petrol/80">
                  <span className="tabular-nums">06</span>
                  <span aria-hidden="true">/</span>
                  <span>{t("landing.final.eyebrow")}</span>
                </p>
                <h2
                  id="final-title"
                  className="mt-4 font-serif text-4xl leading-[0.98] tracking-tight sm:text-5xl lg:text-6xl"
                >
                  {t("landing.final.titleLead")}{" "}
                  <em className={styles.accentOnDark}>{t("landing.final.titleAccent")}</em>
                </h2>
                <p className="mt-5 max-w-xl text-base leading-relaxed text-on-petrol/80">
                  {t("landing.final.description")}
                </p>
              </div>
              <div className="lg:justify-self-end">
                <Button asChild size="lg">
                  <Link href="/painel">
                    {dashboardLabel}
                    <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
