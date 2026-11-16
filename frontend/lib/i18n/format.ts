import type { Locale } from "./constants";

export const INTL_LOCALE: Record<Locale, string> = {
  pt: "pt-BR",
  es: "es",
  en: "en",
};

export function coerceDate(value: Date | string | number): Date {
  if (value instanceof Date) {
    return value;
  }

  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return new Date(`${value}T00:00:00`);
  }

  return new Date(value);
}

export function formatDate(
  value: Date | string | number,
  locale: Locale,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium" },
): string {
  return new Intl.DateTimeFormat(INTL_LOCALE[locale], options).format(coerceDate(value));
}

export function formatNumber(
  value: number,
  locale: Locale,
  options: Intl.NumberFormatOptions = {},
): string {
  return new Intl.NumberFormat(INTL_LOCALE[locale], options).format(value);
}

export function formatCurrency(value: number, locale: Locale, currency = "BRL"): string {
  return new Intl.NumberFormat(INTL_LOCALE[locale], {
    style: "currency",
    currency,
  }).format(value);
}
