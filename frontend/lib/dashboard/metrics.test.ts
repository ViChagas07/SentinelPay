import { describe, expect, it } from "vitest";

import type { AnalysisListItem, Payable } from "@/lib/api/schemas";

import {
  averageScore,
  buildDailySeries,
  buildDashboardSummary,
  buildPendingReceiptSeries,
  buildStripData,
  countBands,
  countPendingConfirmations,
  formatBoundedCount,
  isCompletedAnalysis,
  selectUpcomingPayables,
  sortPayablesByDueDate,
  splitPeriods,
} from "./metrics";

const NOW = new Date("2026-11-16T15:00:00Z");

function analysis(
  id: string,
  createdAt: string,
  score: number | null,
  band: "low" | "attention" | "high" | null,
  status: AnalysisListItem["status"] = "completed",
): AnalysisListItem {
  return {
    id,
    status,
    kind: "boleto",
    score,
    band,
    error_code: null,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function payable(
  id: string,
  dueDate: string,
  status: Payable["status"],
  description = "Conta",
): Payable {
  return {
    id,
    analysis_id: `analysis-${id}`,
    description,
    amount: "100.00",
    due_date: dueDate,
    status,
    created_at: "2026-11-01T12:00:00+00:00",
    updated_at: "2026-11-01T12:00:00+00:00",
  };
}

const ITEMS: AnalysisListItem[] = [
  analysis("a1", "2026-11-15T15:00:00Z", 12, "low"),
  analysis("a2", "2026-11-13T15:00:00Z", 55, "attention"),
  analysis("a3", "2026-11-06T15:00:00Z", 78, "high"),
  analysis("a4", "2026-10-27T15:00:00Z", 32, "low"),
  analysis("a5", "2026-11-16T13:00:00Z", null, null, "processing"),
  analysis("a6", "2026-11-16T14:00:00Z", null, null, "failed"),
  analysis("a7", "2026-10-12T15:00:00Z", 60, "attention"),
  analysis("a8", "2026-10-07T15:00:00Z", 70, "high"),
  analysis("a9", "2026-09-27T15:00:00Z", 80, "high"),
];

describe("isCompletedAnalysis", () => {
  it("accepts completed and degraded analyses with score and band", () => {
    expect(isCompletedAnalysis(ITEMS[0])).toBe(true);
    expect(isCompletedAnalysis(ITEMS[4])).toBe(false);
    expect(isCompletedAnalysis(ITEMS[5])).toBe(false);
  });

  it("rejects a completed analysis without score", () => {
    expect(isCompletedAnalysis(analysis("x", NOW.toISOString(), null, null))).toBe(false);
  });
});

describe("averageScore", () => {
  it("averages only completed analyses", () => {
    expect(averageScore(ITEMS.slice(0, 6))).toBeCloseTo(44.25);
  });

  it("returns null when there is no completed analysis", () => {
    expect(averageScore([])).toBeNull();
    expect(averageScore([ITEMS[4], ITEMS[5]])).toBeNull();
  });
});

describe("periods and bands", () => {
  it("splits current and previous windows", () => {
    const { current, previous } = splitPeriods(ITEMS, 30, NOW);

    expect(current.map((item) => item.id)).toEqual(["a1", "a2", "a3", "a4", "a5", "a6"]);
    expect(previous.map((item) => item.id)).toEqual(["a7", "a8", "a9"]);
  });

  it("counts bands of completed analyses", () => {
    expect(countBands(ITEMS.slice(0, 6))).toEqual({ low: 2, attention: 1, high: 1 });
  });
});

describe("buildDashboardSummary", () => {
  it("calculates average, comparison, conformity and counts", () => {
    const summary = buildDashboardSummary(ITEMS, 30, NOW, "UTC");

    expect(summary.currentAverage).toBeCloseTo(44.25);
    expect(summary.previousAverage).toBeCloseTo(70);
    expect(summary.delta).toBeCloseTo(-25.75);
    expect(summary.conformity).toBeCloseTo(50);
    expect(summary.analyzedCount).toBe(4);
    expect(summary.highRiskCount).toBe(1);
    expect(summary.flaggedCount).toBe(2);
  });

  it("returns null aggregates when the period has no completed analysis", () => {
    const summary = buildDashboardSummary([ITEMS[4], ITEMS[5]], 30, NOW, "UTC");

    expect(summary.currentAverage).toBeNull();
    expect(summary.conformity).toBeNull();
    expect(summary.delta).toBeNull();
    expect(summary.analyzedCount).toBe(0);
  });

  it("builds a full daily strip and series", () => {
    const summary = buildDashboardSummary(ITEMS, 30, NOW, "UTC");

    expect(summary.strip).toHaveLength(30);
    expect(summary.documentsSeries).toHaveLength(30);
    expect(summary.highRiskSeries).toHaveLength(30);
    expect(summary.strip.reduce((total, point) => total + point.low, 0)).toBe(2);
    expect(summary.strip.reduce((total, point) => total + point.attention, 0)).toBe(1);
    expect(summary.strip.reduce((total, point) => total + point.high, 0)).toBe(1);
    expect(summary.documentsSeries.reduce((total, value) => total + value, 0)).toBe(4);
    expect(summary.highRiskSeries.reduce((total, value) => total + value, 0)).toBe(1);
  });
});

describe("daily series", () => {
  it("uses the user time zone to assign the day in the strip", () => {
    const boundary = new Date("2026-11-16T02:30:00Z");
    const items = [analysis("x", "2026-11-16T02:00:00Z", 10, "low")];
    const utc = buildStripData(items, 2, boundary, "UTC");
    const saoPaulo = buildStripData(items, 2, boundary, "America/Sao_Paulo");

    expect(utc.find((point) => point.low === 1)?.date).toBe("2026-11-16");
    expect(saoPaulo.find((point) => point.low === 1)?.date).toBe("2026-11-15");
  });

  it("builds series with zeros for days without analyses", () => {
    const series = buildDailySeries(ITEMS.slice(0, 4), 3, NOW, "UTC");
    const strip = buildStripData(ITEMS.slice(0, 4), 3, NOW, "UTC");

    expect(series).toHaveLength(3);
    expect(strip).toHaveLength(3);
    expect(strip.every((point) => point.low >= 0)).toBe(true);
  });
});

describe("payables", () => {
  const payables = [
    payable("p3", "2026-11-19", "pending_confirmation"),
    payable("p1", "2026-11-14", "overdue"),
    payable("p2", "2026-11-16", "pending_confirmation"),
    payable("p4", "2026-11-26", "pending"),
  ];

  it("sorts by due date ascending", () => {
    expect(sortPayablesByDueDate(payables).map((item) => item.id)).toEqual([
      "p1",
      "p2",
      "p3",
      "p4",
    ]);
  });

  it("selects the nearest due dates", () => {
    expect(selectUpcomingPayables(payables, 3).map((item) => item.id)).toEqual(["p1", "p2", "p3"]);
  });

  it("counts pending confirmations", () => {
    expect(countPendingConfirmations(payables)).toBe(2);
  });

  it("builds a forward-looking pending series", () => {
    const series = buildPendingReceiptSeries(payables, 14, NOW, "UTC");

    expect(series).toHaveLength(14);
    expect(series[0]).toBe(1);
    expect(series[3]).toBe(1);
    expect(series.reduce((total, value) => total + value, 0)).toBe(2);
  });
});

describe("formatBoundedCount", () => {
  it("marks truncated counts with a plus", () => {
    expect(formatBoundedCount(2, false)).toBe("2");
    expect(formatBoundedCount(2, true)).toBe("2+");
    expect(formatBoundedCount(0, false)).toBe("0");
  });
});
