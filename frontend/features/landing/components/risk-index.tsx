"use client";

import { type CSSProperties, useId, useState } from "react";

import { useI18n } from "@/lib/i18n/provider";
import { getRiskPresentation } from "@/lib/risk/presentation";
import { bandForScore } from "@/lib/risk/ruler";
import type { TranslationKey } from "@/lib/i18n";

import { SectionHeading } from "./section-heading";
import styles from "../landing.module.css";

const EXPLANATION_KEYS: Record<"low" | "attention" | "high", TranslationKey> = {
  low: "landing.risk.low",
  attention: "landing.risk.attention",
  high: "landing.risk.high",
};

export function RiskIndex() {
  const { t } = useI18n();
  const sliderId = useId();
  const [score, setScore] = useState(50);
  const band = bandForScore(score);
  const presentation = getRiskPresentation(band);
  const rangeStyle = { "--risk-color": presentation.color } as CSSProperties;

  return (
    <section
      id="indice-risco"
      aria-labelledby="indice-risco-title"
      className="scroll-mt-24 border-b border-border bg-landing"
    >
      <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 sm:py-24">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:items-start lg:gap-16">
          <div>
            <SectionHeading
              id="indice-risco-title"
              number="04"
              label={t("landing.risk.eyebrow")}
              title={t("landing.risk.titleLead")}
              accent={t("landing.risk.titleAccent")}
              description={t("landing.risk.description")}
            />
            <p
              id={`${sliderId}-caveat`}
              className="mt-6 max-w-md border-l-2 border-petrol-500/50 pl-4 text-sm leading-relaxed text-muted-foreground"
            >
              {t("landing.risk.caveat")}
            </p>
          </div>

          <div className="min-w-0 rounded-[6px] border border-border bg-surface p-5 sm:p-7">
            <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
              <div>
                <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
                  {t("landing.risk.score")}
                </p>
                <p className="mt-2 font-mono text-6xl leading-none tabular-nums">{score}</p>
              </div>
              <div className="text-right">
                <p className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
                  {t("landing.risk.classLabel")}
                </p>
                <p className="mt-2 text-lg font-medium">{t(presentation.labelKey)}</p>
              </div>
            </div>

            <div className="mt-6">
              <label
                htmlFor={sliderId}
                className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground"
              >
                {t("landing.risk.sliderLabel")}
              </label>
              <p id={`${sliderId}-help`} className="mt-1 text-xs text-muted-foreground">
                {t("landing.risk.explore")}
              </p>
              <input
                id={sliderId}
                type="range"
                min={0}
                max={100}
                step={1}
                value={score}
                aria-valuetext={t("landing.risk.valueText", {
                  score,
                  band: t(presentation.labelKey),
                })}
                aria-describedby={`${sliderId}-help ${sliderId}-caveat`}
                onChange={(event) => setScore(Number(event.target.value))}
                className={`${styles.range} mt-3`}
                style={rangeStyle}
              />
              <div
                className="relative mt-1 h-3 font-mono text-[0.6rem] text-muted-foreground tabular-nums"
                aria-hidden="true"
              >
                <span className="absolute left-0">0</span>
                <span className="absolute left-[40%] -translate-x-1/2">40</span>
                <span className="absolute left-[70%] -translate-x-1/2">70</span>
                <span className="absolute right-0">100</span>
              </div>
            </div>

            <div className="mt-6 border-t border-border pt-5">
              <p
                className="text-sm leading-relaxed text-muted-foreground"
                aria-live="polite"
                aria-atomic="true"
              >
                {t(EXPLANATION_KEYS[band])}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
