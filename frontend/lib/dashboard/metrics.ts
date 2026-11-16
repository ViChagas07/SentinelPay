import type { AnalysisListItem, Payable } from "@/lib/api/schemas";

import { dateKeyInTimeZone, dateKeysForPeriod, dateKeysFromToday } from "./date";

const DAY_MS = 86_400_000;

export type RiskDistributionPoint = {
  date: string;
  low: number;
  attention: number;
  high: number;
};

export type DashboardBands = {
  low: number;
  attention: number;
  high: number;
};

export type DashboardSummary = {
  current: AnalysisListItem[];
  previous: AnalysisListItem[];
  currentCompleted: AnalysisListItem[];
  previousCompleted: AnalysisListItem[];
  currentAverage: number | null;
  previousAverage: number | null;
  delta: number | null;
  bands: DashboardBands;
  conformity: number | null;
  analyzedCount: number;
  highRiskCount: number;
  flaggedCount: number;
  strip: RiskDistributionPoint[];
  documentsSeries: number[];
  highRiskSeries: number[];
};

export function isCompletedAnalysis(
  item: AnalysisListItem,
): item is AnalysisListItem & { score: number; band: "low" | "attention" | "high" } {
  return (
    (item.status === "completed" || item.status === "degraded") &&
    item.score !== null &&
    item.band !== null
  );
}

export function averageScore(items: readonly AnalysisListItem[]): number | null {
  const scores = items.filter(isCompletedAnalysis).map((item) => item.score);

  if (scores.length === 0) {
    return null;
  }

  return scores.reduce((total, score) => total + score, 0) / scores.length;
}

export function splitPeriods(
  items: readonly AnalysisListItem[],
  periodDays: number,
  now: Date,
): { current: AnalysisListItem[]; previous: AnalysisListItem[] } {
  const periodMs = Math.max(1, periodDays) * DAY_MS;
  const currentStart = now.getTime() - periodMs;
  const previousStart = now.getTime() - periodMs * 2;

  return {
    current: items.filter((item) => {
      const created = new Date(item.created_at).getTime();
      return created >= currentStart && created <= now.getTime();
    }),
    previous: items.filter((item) => {
      const created = new Date(item.created_at).getTime();
      return created >= previousStart && created < currentStart;
    }),
  };
}

export function countBands(items: readonly AnalysisListItem[]): DashboardBands {
  const bands: DashboardBands = { low: 0, attention: 0, high: 0 };

  for (const item of items) {
    if (isCompletedAnalysis(item)) {
      bands[item.band] += 1;
    }
  }

  return bands;
}

export function buildDailySeries(
  items: readonly AnalysisListItem[],
  periodDays: number,
  now: Date,
  timeZone: string,
): number[] {
  const keys = dateKeysForPeriod(periodDays, now, timeZone);
  const counts = new Map(keys.map((key) => [key, 0]));

  for (const item of items) {
    const key = dateKeyInTimeZone(item.created_at, timeZone);

    if (counts.has(key)) {
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }

  return keys.map((key) => counts.get(key) ?? 0);
}

export function buildStripData(
  items: readonly AnalysisListItem[],
  periodDays: number,
  now: Date,
  timeZone: string,
): RiskDistributionPoint[] {
  const keys = dateKeysForPeriod(periodDays, now, timeZone);
  const points = new Map<string, RiskDistributionPoint>(
    keys.map((key) => [key, { date: key, low: 0, attention: 0, high: 0 }]),
  );

  for (const item of items) {
    if (!isCompletedAnalysis(item)) {
      continue;
    }

    const key = dateKeyInTimeZone(item.created_at, timeZone);
    const point = points.get(key);

    if (point) {
      point[item.band] += 1;
    }
  }

  return keys.map((key) => points.get(key) ?? { date: key, low: 0, attention: 0, high: 0 });
}

export function buildDashboardSummary(
  items: readonly AnalysisListItem[],
  periodDays: number,
  now: Date,
  timeZone: string,
): DashboardSummary {
  const { current, previous } = splitPeriods(items, periodDays, now);
  const currentCompleted = current.filter(isCompletedAnalysis);
  const previousCompleted = previous.filter(isCompletedAnalysis);
  const currentAverage = averageScore(currentCompleted);
  const previousAverage = averageScore(previousCompleted);
  const bands = countBands(currentCompleted);
  const total = currentCompleted.length;

  return {
    current,
    previous,
    currentCompleted,
    previousCompleted,
    currentAverage,
    previousAverage,
    delta:
      currentAverage !== null && previousAverage !== null ? currentAverage - previousAverage : null,
    bands,
    conformity: total > 0 ? (bands.low / total) * 100 : null,
    analyzedCount: total,
    highRiskCount: bands.high,
    flaggedCount: bands.attention + bands.high,
    strip: buildStripData(currentCompleted, periodDays, now, timeZone),
    documentsSeries: buildDailySeries(currentCompleted, periodDays, now, timeZone),
    highRiskSeries: buildDailySeries(
      currentCompleted.filter((item) => item.band === "high"),
      periodDays,
      now,
      timeZone,
    ),
  };
}

export function sortPayablesByDueDate(payables: readonly Payable[]): Payable[] {
  return [...payables].sort(
    (left, right) => left.due_date.localeCompare(right.due_date) || left.id.localeCompare(right.id),
  );
}

export function selectUpcomingPayables(payables: readonly Payable[], limit: number): Payable[] {
  return sortPayablesByDueDate(payables).slice(0, Math.max(0, limit));
}

export function countPendingConfirmations(payables: readonly Payable[]): number {
  return payables.filter((payable) => payable.status === "pending_confirmation").length;
}

export function buildPendingReceiptSeries(
  payables: readonly Payable[],
  days: number,
  now: Date,
  timeZone: string,
): number[] {
  const keys = dateKeysFromToday(days, now, timeZone);
  const counts = new Map(keys.map((key) => [key, 0]));

  for (const payable of payables) {
    if (payable.status === "pending_confirmation" && counts.has(payable.due_date)) {
      counts.set(payable.due_date, (counts.get(payable.due_date) ?? 0) + 1);
    }
  }

  return keys.map((key) => counts.get(key) ?? 0);
}

export function formatBoundedCount(count: number, truncated: boolean): string {
  const safeCount = Math.max(0, Math.floor(count));
  return truncated ? `${safeCount}+` : String(safeCount);
}
