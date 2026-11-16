import { describe, expect, it } from "vitest";

import { isThemeMode, resolveThemeMode } from "./constants";

describe("theme", () => {
  it("accepts only the three supported modes", () => {
    expect(isThemeMode("system")).toBe(true);
    expect(isThemeMode("light")).toBe(true);
    expect(isThemeMode("dark")).toBe(true);
    expect(isThemeMode("auto")).toBe(false);
    expect(isThemeMode(undefined)).toBe(false);
  });

  it("defaults invalid or missing values to system", () => {
    expect(resolveThemeMode("dark")).toBe("dark");
    expect(resolveThemeMode("invalid")).toBe("system");
    expect(resolveThemeMode(undefined)).toBe("system");
  });
});
