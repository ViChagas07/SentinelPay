"use client";

import { motion, useReducedMotion } from "motion/react";

import type { RiskBand } from "@/lib/api/schemas";
import { useI18n } from "@/lib/i18n/provider";
import { getRiskPresentation } from "@/lib/risk/presentation";
import { RISK_BAND_LAYOUT, clampScore, scoreToPercent } from "@/lib/risk/ruler";
import { cn } from "@/lib/utils";

export type RiskRulerVariant = "compact" | "medium" | "large";

export type RiskRulerProps = {
  score: number;
  band: RiskBand;
  variant?: RiskRulerVariant;
  className?: string;
};

const TRACK_HEIGHT: Record<RiskRulerVariant, string> = {
  compact: "h-1",
  medium: "h-1.5",
  large: "h-2",
};

function BandLabels() {
  const { t } = useI18n();

  return (
    <div
      className="grid w-full gap-1 font-mono text-[0.6rem] leading-tight text-muted-foreground"
      style={{ gridTemplateColumns: "40fr 30fr 30fr" }}
    >
      {RISK_BAND_LAYOUT.map((band) => {
        const presentation = getRiskPresentation(band.band);

        return (
          <div
            key={band.band}
            className={cn(
              "min-w-0",
              band.band === "low" && "text-left",
              band.band === "attention" && "text-center",
              band.band === "high" && "text-right",
            )}
          >
            <span className="block truncate">{t(presentation.labelKey)}</span>
            <span className="block tabular-nums">{band.rangeLabel}</span>
          </div>
        );
      })}
    </div>
  );
}

function TickLabels() {
  return (
    <div className="relative mt-1 h-3 font-mono text-[0.6rem] text-muted-foreground tabular-nums">
      <span className="absolute left-0">0</span>
      <span className="absolute left-1/4 -translate-x-1/2">25</span>
      <span className="absolute left-1/2 -translate-x-1/2">50</span>
      <span className="absolute left-3/4 -translate-x-1/2">75</span>
      <span className="absolute right-0">100</span>
    </div>
  );
}

function RulerTrack({
  score,
  band,
  variant,
}: Readonly<Pick<RiskRulerProps, "score" | "band" | "variant">>) {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion() ?? false;
  const presentation = getRiskPresentation(band);
  const safeScore = clampScore(score);
  const percent = scoreToPercent(score);
  const transition = reduceMotion
    ? { duration: 0 }
    : { type: "spring" as const, stiffness: 120, damping: 18 };

  return (
    <div
      className="relative w-full min-w-0"
      role="meter"
      aria-label={t("design.riskRuler.score")}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={safeScore}
      aria-valuetext={t("design.riskRuler.aria", {
        score: safeScore,
        band: t(presentation.labelKey),
      })}
    >
      <div
        className={cn(
          "flex w-full overflow-hidden rounded-[2px] border border-border",
          TRACK_HEIGHT[variant ?? "medium"],
        )}
      >
        {RISK_BAND_LAYOUT.map((segment) => {
          const segmentPresentation = getRiskPresentation(segment.band);

          return (
            <span
              key={segment.band}
              className="h-full border-r border-border last:border-r-0"
              style={{
                width: `${segment.width}%`,
                backgroundColor: `color-mix(in srgb, ${segmentPresentation.color} 55%, var(--surface))`,
              }}
              aria-hidden="true"
            />
          );
        })}
      </div>
      <div className="relative mt-1 flex justify-between" aria-hidden="true">
        {[0, 25, 50, 75, 100].map((tick) => (
          <span key={tick} className="h-1.5 w-px bg-border" />
        ))}
      </div>
      <motion.span
        className="pointer-events-none absolute -top-2 z-10 flex -translate-x-1/2 flex-col items-center"
        initial={{ left: "0%" }}
        animate={{ left: `${percent}%` }}
        transition={transition}
        aria-hidden="true"
      >
        <span
          className="block size-2 rotate-45 border border-surface"
          style={{ backgroundColor: presentation.color }}
        />
        <span className="block h-4 w-px" style={{ backgroundColor: presentation.color }} />
      </motion.span>
    </div>
  );
}

export function RiskRuler({ score, band, variant = "medium", className }: RiskRulerProps) {
  const { t } = useI18n();
  const presentation = getRiskPresentation(band);
  const safeScore = clampScore(score);

  if (variant === "compact") {
    return (
      <div
        className={cn("flex w-full min-w-0 items-center gap-3", className)}
        data-variant="compact"
      >
        <span className="shrink-0 font-mono text-sm tabular-nums">{safeScore}</span>
        <div className="min-w-0 flex-1">
          <RulerTrack score={score} band={band} variant="compact" />
        </div>
        <span className="shrink-0 text-xs font-medium">{t(presentation.labelKey)}</span>
      </div>
    );
  }

  const isLarge = variant === "large";

  return (
    <div className={cn("flex w-full min-w-0 flex-col gap-2", className)} data-variant={variant}>
      <div className="flex items-end justify-between gap-4">
        <div className="flex min-w-0 items-baseline gap-2">
          <span
            className={cn(
              "font-mono tabular-nums",
              isLarge ? "text-4xl leading-none" : "text-2xl leading-none",
            )}
          >
            {safeScore}
          </span>
          <span className="font-mono text-[0.65rem] uppercase tracking-[0.2em] text-muted-foreground">
            {t("design.riskRuler.score")}
          </span>
        </div>
        <span className={cn("shrink-0 font-medium", isLarge ? "text-base" : "text-sm")}>
          {t(presentation.labelKey)}
        </span>
      </div>
      <RulerTrack score={score} band={band} variant={variant} />
      {isLarge ? <TickLabels /> : null}
      <BandLabels />
    </div>
  );
}
