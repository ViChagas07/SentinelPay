"use client";

import { BrandLoader } from "@/components/brand/brand-loader";
import { useI18n } from "@/lib/i18n/provider";

export default function Loading() {
  const { t } = useI18n();

  return (
    <main
      id="conteudo"
      className="mx-auto flex min-h-dvh w-full max-w-6xl flex-col justify-center gap-8 px-5 py-24 sm:px-8"
      aria-busy="true"
      aria-live="polite"
    >
      <span className="sr-only">{t("loading.label")}</span>
      <BrandLoader className="size-10" />
      <div className="space-y-4">
        <div className="h-3 w-28 rounded-[6px] bg-surface-elevated" />
        <div className="h-14 w-full max-w-3xl rounded-[6px] bg-surface-elevated" />
        <div className="h-14 w-4/5 max-w-2xl rounded-[6px] bg-surface-elevated" />
        <div className="h-5 w-full max-w-xl rounded-[6px] bg-surface" />
        <div className="h-5 w-3/5 max-w-lg rounded-[6px] bg-surface" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="h-36 rounded-[6px] border border-border bg-surface" />
        <div className="h-36 rounded-[6px] border border-border bg-surface" />
        <div className="h-36 rounded-[6px] border border-border bg-surface" />
      </div>
    </main>
  );
}
