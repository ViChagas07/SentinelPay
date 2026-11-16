"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { useI18n } from "@/lib/i18n/provider";

export function ComingSoon({ title }: Readonly<{ title: string }>) {
  const { t } = useI18n();
  const pathname = usePathname();

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-16 sm:px-8">
      <Eyebrow number="01" label={t("shell.placeholder.eyebrow")} />
      <h1 className="mt-4 font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
        {t("shell.placeholder.title")}
      </h1>
      <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
        {t("shell.placeholder.description")}
      </p>
      <div className="mt-8 rounded-[6px] border border-border bg-card p-5">
        <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
          {pathname}
        </p>
        <p className="mt-2 text-sm font-medium">{title}</p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          {t("shell.placeholder.gapNote")}
        </p>
      </div>
      <div className="mt-8">
        <Button asChild variant="outline">
          <Link href="/painel">{t("shell.placeholder.backToPanel")}</Link>
        </Button>
      </div>
    </div>
  );
}
