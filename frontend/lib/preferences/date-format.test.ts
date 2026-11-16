import { describe, expect, it } from "vitest";

import { formatDateWithPreference, isDateFormat, resolveDateFormat } from "./date-format";

const DATE = new Date("2026-11-16T12:00:00Z");

describe("date format preference", () => {
  it("accepts only the supported values", () => {
    expect(isDateFormat("dmy")).toBe(true);
    expect(isDateFormat("mdy")).toBe(true);
    expect(isDateFormat("iso")).toBe(true);
    expect(isDateFormat("auto")).toBe(true);
    expect(isDateFormat("ymd")).toBe(false);
    expect(resolveDateFormat("invalid")).toBe("auto");
    expect(resolveDateFormat(undefined)).toBe("auto");
  });

  it("keeps the locale order in auto mode", () => {
    expect(
      formatDateWithPreference(DATE, "en", "auto", {
        dateStyle: "medium",
        timeZone: "UTC",
      }),
    ).toBe("Nov 16, 2026");
  });

  it("applies day first, month first and ISO order", () => {
    const base = { dateStyle: "short" as const, timeZone: "UTC" };

    expect(formatDateWithPreference(DATE, "en", "dmy", base)).toBe("16/11/2026");
    expect(formatDateWithPreference(DATE, "en", "mdy", base)).toBe("11/16/2026");
    expect(formatDateWithPreference(DATE, "en", "iso", base)).toBe("2026-11-16");
  });

  it("preserves the time when the caller asked for it", () => {
    expect(
      formatDateWithPreference(DATE, "en", "dmy", {
        dateStyle: "short",
        timeStyle: "short",
        timeZone: "UTC",
      }),
    ).toBe("16/11/2026, 12:00 PM");
  });

  it("leaves custom explicit date fields untouched", () => {
    expect(
      formatDateWithPreference(DATE, "en", "dmy", {
        day: "2-digit",
        month: "short",
        timeZone: "UTC",
      }),
    ).toBe("Nov 16");
  });
});
