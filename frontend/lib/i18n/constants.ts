export const LOCALES = ["pt", "es", "en"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "pt";

export const LOCALE_COOKIE = "locale";

export const HTML_LANG: Record<Locale, string> = {
  pt: "pt-BR",
  es: "es",
  en: "en",
};

export function isLocale(value: string | undefined | null): value is Locale {
  return value === "pt" || value === "es" || value === "en";
}

export function resolveLocale(value: string | undefined | null): Locale {
  return isLocale(value) ? value : DEFAULT_LOCALE;
}
