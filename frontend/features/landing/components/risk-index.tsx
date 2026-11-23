"use client";

import { type CSSProperties, useId, useState } from "react";

import { useI18n } from "@/lib/i18n/provider";
import { getLandingRiskPalette, getRiskPresentation } from "@/lib/risk/presentation";
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
  const palette = getLandingRiskPalette(band);
  const rangeStyle = { "--risk-color": palette.color } as CSSProperties;
  const fillStyle: CSSProperties = {
    width: `calc(0.55rem + (100% - 1.1rem) * ${score / 100})`,
    backgroundColor: palette.color,
  };
  const badgeStyle: CSSProperties = {
    backgroundColor: palette.color,
    borderColor: palette.color,
    color: palette.foreground,
  };

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
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
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
                <span
                  className="mt-2 inline-flex items-center gap-2 rounded-[4px] border px-3 py-1.5 text-base font-semibold transition-colors"
                  style={badgeStyle}
                >
                  <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
                  {t(presentation.labelKey)}
                </span>
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
              <div className="relative mt-2">
                <div
                  className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2"
                  aria-hidden="true"
                >
                  <div className="relative h-2.5 w-full overflow-hidden rounded-[2px] border border-border bg-surface-elevated">
                    <span
                      className="absolute inset-y-0 left-0 transition-colors duration-150 ease-out"
                      style={fillStyle}
                    />
                    <span className="absolute inset-y-0 left-[40%] w-px bg-border" />
                    <span className="absolute inset-y-0 left-[70%] w-px bg-border" />
                  </div>
                </div>
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
                  className={`${styles.range} relative z-10 w-full`}
                  style={rangeStyle}
                />
              </div>
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
