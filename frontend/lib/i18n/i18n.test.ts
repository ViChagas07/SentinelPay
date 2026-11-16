import { describe, expect, it } from "vitest";

import { resolveLocale } from "./constants";
import { en, es, pt } from "./dictionaries";
import { formatCurrency, formatDate, formatNumber } from "./format";
import { translate } from "./translate";

describe("i18n", () => {
  it("keeps the three dictionaries in sync", () => {
    const ptKeys = Object.keys(pt).sort();
    expect(Object.keys(es).sort()).toEqual(ptKeys);
    expect(Object.keys(en).sort()).toEqual(ptKeys);
  });

  it("translates and falls back to Portuguese for unknown locales", () => {
    expect(translate("pt", "risk.low")).toBe("Baixo");
    expect(translate("es", "risk.low")).toBe("Bajo");
    expect(translate("en", "risk.low")).toBe("Low");
    expect(resolveLocale("fr")).toBe("pt");
    expect(resolveLocale("es")).toBe("es");
    expect(resolveLocale(undefined)).toBe("pt");
  });

  it("returns labels for the selected locale", () => {
    expect(translate("pt", "common.skipToContent")).toBe("Pular para o conteúdo");
    expect(translate("en", "common.backHome")).toBe("Back to home");
  });

  it("formats BRL, numbers and dates with Intl", () => {
    expect(formatCurrency(1234.56, "pt")).toContain("1.234,56");
    expect(formatCurrency(1234.56, "pt")).toContain("R$");
    expect(formatNumber(1234.5, "en")).toBe("1,234.5");
    expect(formatDate("2026-11-15", "pt")).toContain("2026");
  });
});
