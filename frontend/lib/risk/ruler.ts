import type { RiskBand } from "@/lib/api/schemas";

export type RiskBandLayout = {
  band: RiskBand;
  start: number;
  end: number;
  width: number;
  rangeLabel: string;
};

export const RISK_BAND_LAYOUT: readonly RiskBandLayout[] = [
  { band: "low", start: 0, end: 40, width: 40, rangeLabel: "0-39" },
  { band: "attention", start: 40, end: 70, width: 30, rangeLabel: "40-69" },
  { band: "high", start: 70, end: 100, width: 30, rangeLabel: "70-100" },
];

export function clampScore(score: number): number {
  if (!Number.isFinite(score)) {
    return 0;
  }

  return Math.min(100, Math.max(0, score));
}

export function scoreToPercent(score: number): number {
  return clampScore(score);
}

export function bandForScore(score: number): RiskBand {
  const safeScore = clampScore(score);

  if (safeScore < 40) {
    return "low";
  }

  if (safeScore < 70) {
    return "attention";
  }

  return "high";
}
