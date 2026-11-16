import { describe, expect, it } from "vitest";

import { alertIconHref, buildAlertTitle, countHighRiskAlerts, formatBadgeCount } from "./alerts";

function page(count: number, next: string | null) {
  return {
    items: Array.from({ length: count }, (_, index) => ({
      id: `n-${index}`,
      type: "high_risk_detected" as const,
      payload: {},
      read: false,
      read_at: null,
      created_at: null,
    })),
    next_cursor: next,
  };
}

describe("shell alerts", () => {
  it("counts every page until the cursor ends", async () => {
    const cursors: Array<string | null> = [];
    const result = await countHighRiskAlerts(async (cursor) => {
      cursors.push(cursor);
      return cursor === null ? page(2, "next") : page(3, null);
    });

    expect(result).toEqual({ count: 5, truncated: false });
    expect(cursors).toEqual([null, "next"]);
  });

  it("marks the result as truncated when the safety cap is reached", async () => {
    const result = await countHighRiskAlerts(async () => page(2, "always-next"), 3);
    expect(result).toEqual({ count: 6, truncated: true });
  });

  it("formats the badge and hides it at zero", () => {
    expect(formatBadgeCount(0)).toBeNull();
    expect(formatBadgeCount(3)).toBe("3");
    expect(formatBadgeCount(99)).toBe("99");
    expect(formatBadgeCount(120)).toBe("99+");
  });

  it("builds the alert title and icon", () => {
    const base = { baseTitle: "Painel Principal", appName: "SentinelPay" };

    expect(buildAlertTitle({ ...base, count: 0, truncated: false })).toBe(
      "Painel Principal | SentinelPay",
    );
    expect(buildAlertTitle({ ...base, count: 2, truncated: false })).toBe(
      "(2) Painel Principal | SentinelPay",
    );
    expect(buildAlertTitle({ ...base, count: 500, truncated: true })).toBe(
      "(500+) Painel Principal | SentinelPay",
    );
    expect(alertIconHref(0)).toBe("/icon.svg");
    expect(alertIconHref(1)).toBe("/favicon-alert.svg");
  });
});
