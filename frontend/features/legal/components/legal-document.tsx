"use client";

import { ArrowUp, Check, Link2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Eyebrow } from "@/components/ui/eyebrow";
import { PageTransition } from "@/components/ui/motion/page-transition";
import { useI18n } from "@/lib/i18n/provider";
import type { LegalDocument } from "@/lib/legal/content/types";
import type { LegalIdentity } from "@/lib/legal/identity";
import { LEGAL_UPDATED_AT, LEGAL_VERSION, type LegalDocumentKind } from "@/lib/legal/version";

import { LegalBlocks } from "./legal-blocks";
import { LegalToc } from "./legal-toc";

export type LegalDocumentViewProps = {
  kind: LegalDocumentKind;
  content: LegalDocument;
  identity: LegalIdentity;
};

function sectionNumber(index: number): string {
  return String(index + 1).padStart(2, "0");
}

function scrollToTop(): void {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
}

function FloatingBackToTop() {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 700);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (!visible) {
    return null;
  }

  return (
    <button
      type="button"
      aria-label={t("legal.backToTop")}
      onClick={scrollToTop}
      className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-[6px] border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background print:hidden"
    >
      <ArrowUp className="size-3.5" aria-hidden="true" />
      <span className="hidden sm:inline">{t("legal.backToTop")}</span>
    </button>
  );
}

export function LegalDocumentView({ kind, content, identity }: LegalDocumentViewProps) {
  const { t, formatDate } = useI18n();
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copyFailed, setCopyFailed] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const copyAnchor = useCallback(async (id: string) => {
    const url = `${window.location.origin}${window.location.pathname}#${id}`;

    try {
      await navigator.clipboard.writeText(url);
      setCopyFailed(false);
      setCopiedId(id);
    } catch {
      setCopiedId(null);
      setCopyFailed(true);
    }

    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = window.setTimeout(() => {
      setCopiedId(null);
      setCopyFailed(false);
    }, 2400);
  }, []);

  const relatedLabel = kind === "terms" ? t("legal.relatedPrivacy") : t("legal.relatedTerms");
  const relatedHref = kind === "terms" ? "/privacidade" : "/termos";

  return (
    <PageTransition>
      <p className="sr-only" aria-live="polite">
        {copiedId ? t("legal.copied") : copyFailed ? t("legal.copyFailed") : ""}
      </p>

      <header className="max-w-3xl">
        <Eyebrow number={kind === "terms" ? "01" : "02"} label={t("legal.eyebrow")} />
        <h1 className="mt-4 font-serif text-4xl leading-[1.05] tracking-tight sm:text-5xl">
          {content.title}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground">
          {content.subtitle}
        </p>

        <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-2 font-mono text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
          <div className="flex gap-2">
            <dt>{t("legal.updatedLabel")}</dt>
            <dd>
              <time dateTime={LEGAL_UPDATED_AT}>{formatDate(LEGAL_UPDATED_AT)}</time>
            </dd>
          </div>
          <div className="flex gap-2">
            <dt>{t("legal.versionLabel")}</dt>
            <dd>{LEGAL_VERSION}</dd>
          </div>
        </dl>

        {content.notice ? (
          <p className="mt-6 rounded-[6px] border border-border bg-surface-elevated p-4 text-sm leading-relaxed text-foreground/80">
            {content.notice}
          </p>
        ) : null}

        <nav
          aria-label={t("legal.related")}
          className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm"
        >
          <Link
            href={relatedHref}
            className="inline-flex min-h-9 items-center text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            {relatedLabel}
          </Link>
          <Link
            href="/account"
            className="inline-flex min-h-9 items-center text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            {t("legal.relatedAccount")}
          </Link>
        </nav>
      </header>

      <div className="mt-10 grid gap-10 lg:mt-12 lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-14">
        <LegalToc sections={content.sections} />

        <article className="min-w-0 max-w-[70ch]">
          <div className="space-y-10">
            {content.sections.map((section, index) => (
              <section
                key={section.id}
                id={section.id}
                aria-labelledby={`${section.id}-title`}
                className="scroll-mt-24 border-t border-border pt-8 first:border-t-0 first:pt-0"
              >
                <div className="flex items-start gap-3">
                  <span
                    aria-hidden="true"
                    className="mt-1.5 shrink-0 font-mono text-[0.65rem] tabular-nums tracking-[0.18em] text-muted-foreground"
                  >
                    {sectionNumber(index)}
                  </span>
                  <h2
                    id={`${section.id}-title`}
                    className="min-w-0 font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
                  >
                    {section.title}
                  </h2>
                  <button
                    type="button"
                    onClick={() => void copyAnchor(section.id)}
                    aria-label={t("legal.copyAnchor", { title: section.title })}
                    className="ml-auto mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-[4px] text-muted-foreground transition-colors hover:bg-surface-elevated hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background print:hidden"
                  >
                    {copiedId === section.id ? (
                      <Check className="size-4" aria-hidden="true" />
                    ) : (
                      <Link2 className="size-4" aria-hidden="true" />
                    )}
                  </button>
                </div>

                <div className="mt-4 space-y-4 sm:pl-10">
                  <LegalBlocks blocks={section.blocks} identity={identity} />
                </div>
              </section>
            ))}
          </div>

          <div className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
            <Link
              href="/"
              className="inline-flex min-h-9 items-center text-sm text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
            >
              {t("common.backHome")}
            </Link>
            <button
              type="button"
              onClick={scrollToTop}
              className="inline-flex min-h-9 items-center gap-2 rounded-[4px] border border-border bg-surface px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-surface-elevated focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background print:hidden"
            >
              <ArrowUp className="size-3.5" aria-hidden="true" />
              {t("legal.backToTop")}
            </button>
          </div>
        </article>
      </div>

      <FloatingBackToTop />
    </PageTransition>
  );
}
