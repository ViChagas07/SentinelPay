import { describe, expect, it } from "vitest";

import {
  dateKeyInTimeZone,
  dateKeysForPeriod,
  dateKeysFromToday,
  daysBetweenDateKeys,
  formatDashboardDate,
  formatRelativeTime,
  formatSignedPoints,
  getDueDateRelation,
  resolveTimeZone,
} from "./date";

const NOW = new Date("2026-11-16T15:00:00Z");

describe("resolveTimeZone", () => {
  it("keeps a valid IANA time zone", () => {
    expect(resolveTimeZone("America/Sao_Paulo")).toBe("America/Sao_Paulo");
  });

  it("falls back when the value is missing or invalid", () => {
    expect(resolveTimeZone(null)).toBe("UTC");
    expect(resolveTimeZone(undefined)).toBe("UTC");
    expect(resolveTimeZone("Mars/Olympus")).toBe("UTC");
    expect(resolveTimeZone("", "America/Sao_Paulo")).toBe("America/Sao_Paulo");
  });
});

describe("date keys", () => {
  it("uses the calendar day of the requested time zone", () => {
    const instant = new Date("2026-11-16T02:30:00Z");

    expect(dateKeyInTimeZone(instant, "UTC")).toBe("2026-11-16");
    expect(dateKeyInTimeZone(instant, "America/Sao_Paulo")).toBe("2026-11-15");
  });

  it("returns an empty key for invalid dates", () => {
    expect(dateKeyInTimeZone("not-a-date", "UTC")).toBe("");
  });

  it("builds the period ending today", () => {
    expect(dateKeysForPeriod(3, NOW, "UTC")).toEqual(["2026-11-14", "2026-11-15", "2026-11-16"]);
  });

  it("builds forward-looking day keys", () => {
    expect(dateKeysFromToday(3, NOW, "UTC")).toEqual(["2026-11-16", "2026-11-17", "2026-11-18"]);
  });

  it("calculates whole day differences", () => {
    expect(daysBetweenDateKeys("2026-11-16", "2026-11-19")).toBe(3);
    expect(daysBetweenDateKeys("2026-11-16", "2026-11-14")).toBe(-2);
    expect(daysBetweenDateKeys("invalid", "2026-11-14")).toBeNull();
  });
});

describe("getDueDateRelation", () => {
  it("labels today, tomorrow, future and past dates", () => {
    expect(getDueDateRelation("2026-11-16", "UTC", NOW)).toEqual({ kind: "today", days: 0 });
    expect(getDueDateRelation("2026-11-17", "UTC", NOW)).toEqual({
      kind: "tomorrow",
      days: 1,
    });
    expect(getDueDateRelation("2026-11-19", "UTC", NOW)).toEqual({ kind: "inDays", days: 3 });
    expect(getDueDateRelation("2026-11-15", "UTC", NOW)).toEqual({
      kind: "yesterday",
      days: -1,
    });
    expect(getDueDateRelation("2026-11-14", "UTC", NOW)).toEqual({ kind: "daysAgo", days: 2 });
  });

  it("respects the user time zone at the day boundary", () => {
    const boundary = new Date("2026-11-16T02:30:00Z");

    expect(getDueDateRelation("2026-11-16", "UTC", boundary)).toEqual({
      kind: "today",
      days: 0,
    });
    expect(getDueDateRelation("2026-11-16", "America/Sao_Paulo", boundary)).toEqual({
      kind: "tomorrow",
      days: 1,
    });
  });

  it("returns null for invalid dates", () => {
    expect(getDueDateRelation("16/11/2026", "UTC", NOW)).toBeNull();
  });
});

describe("formatRelativeTime", () => {
  it("formats recent timestamps in the interface language", () => {
    expect(formatRelativeTime("2026-11-16T14:59:45Z", "pt", NOW)).toBe("agora");
    expect(formatRelativeTime("2026-11-16T14:55:00Z", "pt", NOW)).toBe("há 5 minutos");
    expect(formatRelativeTime("2026-11-16T13:00:00Z", "pt", NOW)).toBe("há 2 horas");
    expect(formatRelativeTime("2026-11-13T15:00:00Z", "pt", NOW)).toBe("há 3 dias");
    expect(formatRelativeTime("2026-11-04T15:00:00Z", "pt", NOW)).toBe("há 2 semanas");
  });

  it("formats in Spanish and English", () => {
    expect(formatRelativeTime("2026-11-16T14:55:00Z", "es", NOW)).toBe("hace 5 minutos");
    expect(formatRelativeTime("2026-11-16T14:55:00Z", "en", NOW)).toBe("5 minutes ago");
  });

  it("returns an empty string for invalid timestamps", () => {
    expect(formatRelativeTime("not-a-date", "pt", NOW)).toBe("");
  });
});

describe("formatDashboardDate", () => {
  it("formats the date in the user time zone", () => {
    const date = new Date("2026-11-16T02:30:00Z");

    expect(formatDashboardDate(date, "pt", "America/Sao_Paulo")).toContain(
      "15 de novembro de 2026",
    );
    expect(formatDashboardDate(date, "pt", "UTC")).toContain("16 de novembro de 2026");
  });
});

describe("formatSignedPoints", () => {
  it("shows the sign except for zero", () => {
    expect(formatSignedPoints(4.2, "pt")).toBe("+4");
    expect(formatSignedPoints(-25.75, "pt")).toBe("-26");
    expect(formatSignedPoints(0, "pt")).toBe("0");
  });
});
