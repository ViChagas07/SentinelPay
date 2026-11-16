"use client";

import { useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

import { RiskRuler } from "@/components/ui/risk-ruler";
import type { RiskBand } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import styles from "../landing.module.css";

const DEMO_SCORE = 68;
const DEMO_BAND: RiskBand = "attention";
const DEMO_FINAL_STEP = 3;

function PlaceholderLine({ width }: Readonly<{ width: string }>) {
  return <span className="block h-2 rounded-full bg-border" style={{ width }} aria-hidden="true" />;
}

export function HeroDemo() {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion() ?? false;
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (reduceMotion) {
      const timer = window.setTimeout(() => setStep(DEMO_FINAL_STEP), 0);

      return () => {
        window.clearTimeout(timer);
      };
    }

    const timers = [
      window.setTimeout(() => setStep(0), 0),
      window.setTimeout(() => setStep(1), 900),
      window.setTimeout(() => setStep(2), 1700),
      window.setTimeout(() => setStep(DEMO_FINAL_STEP), 2500),
    ];

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [reduceMotion]);

  const complete = step >= DEMO_FINAL_STEP;

  return (
    <figure className="mx-auto w-full max-w-md lg:ml-auto">
      <div className="rounded-[6px] border border-border bg-surface p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.2em] text-muted-foreground">
            {t("landing.hero.docTitle")}
          </span>
          <span className="inline-flex items-center gap-1.5 font-mono text-[0.6rem] uppercase tracking-[0.18em] text-muted-foreground">
            <span
              className={cn("size-1.5 rounded-full", complete ? "bg-petrol-500" : "bg-petrol-300")}
              aria-hidden="true"
            />
            {complete ? t("landing.hero.readComplete") : t("landing.hero.reading")}
          </span>
        </div>

        <div
          className="relative mt-4 min-h-[280px] overflow-hidden rounded-[4px] border border-border bg-surface-elevated p-4"
          role="group"
          aria-label={t("landing.hero.demoAria")}
        >
          <span className={styles.scanLine} aria-hidden="true" />

          <div className="space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-[0.55rem] uppercase tracking-[0.18em] text-muted-foreground">
                  {t("landing.hero.fieldBeneficiary")}
                </p>
                <div className="mt-2 space-y-1.5">
                  <PlaceholderLine width="80%" />
                  <PlaceholderLine width="55%" />
                </div>
              </div>
              <div className="shrink-0 text-right">
                <p className="font-mono text-[0.55rem] uppercase tracking-[0.18em] text-muted-foreground">
                  {t("landing.hero.fieldTaxId")}
                </p>
                <p className="mt-2 font-mono text-xs tracking-[0.14em] text-muted-foreground">
                  ••.•••.•••/••••-••
                </p>
              </div>
            </div>

            <div>
              <p className="font-mono text-[0.55rem] uppercase tracking-[0.18em] text-muted-foreground">
                {t("landing.hero.fieldLine")}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5" aria-hidden="true">
                {[44, 32, 52, 28, 40, 36].map((width, index) => (
                  <span
                    key={`${width}-${index}`}
                    className="h-2 rounded-full bg-border"
                    style={{ width: `${width}px` }}
                  />
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 border-t border-border pt-3">
              <div>
                <p className="font-mono text-[0.55rem] uppercase tracking-[0.18em] text-muted-foreground">
                  {t("landing.hero.fieldAmount")}
                </p>
                <p className="mt-1.5 font-mono text-sm text-muted-foreground">
                  {t("landing.hero.amountMask")}
                </p>
              </div>
              <div>
                <p className="font-mono text-[0.55rem] uppercase tracking-[0.18em] text-muted-foreground">
                  {t("landing.hero.fieldDueDate")}
                </p>
                <p className="mt-1.5 font-mono text-sm text-muted-foreground">••/••/••••</p>
              </div>
            </div>

            <div
              className="flex h-12 items-end gap-[2px] border-t border-border pt-2"
              aria-hidden="true"
            >
              {Array.from({ length: 40 }).map((_, index) => (
                <span
                  key={index}
                  className="w-[2px] shrink-0 bg-foreground/70"
                  style={{ height: `${18 + ((index * 7) % 26)}px` }}
                />
              ))}
            </div>
          </div>

          {step >= 1 ? (
            <div className={cn("absolute right-2 top-[74px] max-w-[78%]", styles.chipEnter)}>
              <span className="inline-flex items-center gap-1.5 rounded-[4px] border border-risk-high/40 bg-surface px-2 py-1 text-[0.7rem] font-medium leading-tight text-foreground">
                <span className="size-1.5 shrink-0 rounded-full bg-risk-high" aria-hidden="true" />
                {t("landing.hero.evidenceLine")}
              </span>
            </div>
          ) : null}

          {step >= 2 ? (
            <div className={cn("absolute right-2 top-[142px] max-w-[78%]", styles.chipEnter)}>
              <span className="inline-flex items-center gap-1.5 rounded-[4px] border border-risk-high/40 bg-surface px-2 py-1 text-[0.7rem] font-medium leading-tight text-foreground">
                <span className="size-1.5 shrink-0 rounded-full bg-risk-high" aria-hidden="true" />
                {t("landing.hero.evidenceTaxId")}
              </span>
            </div>
          ) : null}
        </div>

        <div className="mt-4 border-t border-border pt-4">
          <RiskRuler
            score={complete ? DEMO_SCORE : 0}
            band={complete ? DEMO_BAND : "low"}
            variant="medium"
          />
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            {t("landing.hero.demoNote")}
          </p>
        </div>
      </div>
      <figcaption className="mt-2 text-center font-mono text-[0.6rem] uppercase tracking-[0.18em] text-muted-foreground">
        {t("landing.hero.demoLabel")}
      </figcaption>
    </figure>
  );
}
