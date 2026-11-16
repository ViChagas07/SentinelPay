import { describe, expect, it } from "vitest";

import { accountPreferencesSchema } from "./preferences";

describe("account preferences schema", () => {
  it("accepts the supported locale, theme and date format", () => {
    expect(
      accountPreferencesSchema.safeParse({
        locale: "pt",
        theme: "system",
        dateFormat: "auto",
      }).success,
    ).toBe(true);
    expect(
      accountPreferencesSchema.safeParse({
        locale: "en",
        theme: "dark",
        dateFormat: "iso",
      }).success,
    ).toBe(true);
  });

  it("rejects unsupported values", () => {
    expect(
      accountPreferencesSchema.safeParse({
        locale: "fr",
        theme: "dark",
        dateFormat: "iso",
      }).success,
    ).toBe(false);
    expect(
      accountPreferencesSchema.safeParse({
        locale: "pt",
        theme: "sepia",
        dateFormat: "iso",
      }).success,
    ).toBe(false);
    expect(
      accountPreferencesSchema.safeParse({
        locale: "pt",
        theme: "dark",
        dateFormat: "ymd",
      }).success,
    ).toBe(false);
  });
});
