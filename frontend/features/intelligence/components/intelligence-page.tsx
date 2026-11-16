"use client";

import { ArrowLeft, BrainCircuit, Layers, MessageSquare, Radar, ScrollText } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { useI18n } from "@/lib/i18n/provider";

const NEXT_ITEMS = [
  { icon: ScrollText, key: "intelligence.next.rules" },
  { icon: Radar, key: "intelligence.next.cases" },
  { icon: Layers, key: "intelligence.next.models" },
  { icon: MessageSquare, key: "intelligence.next.feedback" },
] as const;

export function IntelligencePage() {
  const { t } = useI18n();

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="border-b border-border pb-8">
        <Eyebrow number="05" label={t("intelligence.title")} />
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <h1 className="font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
            {t("intelligence.title")}
          </h1>
          <Badge variant="outline" className="font-mono text-[0.6rem] uppercase tracking-[0.14em]">
            {t("intelligence.status")}
          </Badge>
        </div>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground">
          {t("intelligence.description")}
        </p>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section
          aria-labelledby="intelligence-honest-title"
          className="rounded-[6px] border border-border bg-card p-6 sm:p-8"
        >
          <span className="flex size-11 items-center justify-center rounded-full border border-border bg-surface-elevated">
            <BrainCircuit className="size-5" aria-hidden="true" />
          </span>
          <h2
            id="intelligence-honest-title"
            className="mt-4 font-serif text-2xl leading-tight tracking-tight"
          >
            {t("intelligence.honestTitle")}
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            {t("intelligence.honest")}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {t("intelligence.noData")}
          </p>
          <div className="mt-8">
            <Button asChild variant="outline">
              <Link href="/painel">
                <ArrowLeft aria-hidden="true" />
                {t("intelligence.backToPanel")}
              </Link>
            </Button>
          </div>
        </section>

        <aside aria-labelledby="intelligence-next-title" className="min-w-0">
          <h2
            id="intelligence-next-title"
            className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground"
          >
            {t("intelligence.nextTitle")}
          </h2>
          <ul className="mt-3 divide-y divide-border border-y border-border">
            {NEXT_ITEMS.map((item) => {
              const Icon = item.icon;

              return (
                <li key={item.key} className="flex items-start gap-3 py-3">
                  <Icon
                    className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <span className="min-w-0 text-sm leading-relaxed">{t(item.key)}</span>
                </li>
              );
            })}
          </ul>
        </aside>
      </div>
    </div>
  );
}
