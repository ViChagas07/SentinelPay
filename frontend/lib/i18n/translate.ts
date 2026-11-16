import { DEFAULT_LOCALE, type Locale } from "./constants";
import { dictionaries, type TranslationKey } from "./dictionaries";

export type TranslationParams = Record<string, string | number>;

function interpolate(template: string, params?: TranslationParams): string {
  if (!params) {
    return template;
  }

  return template.replace(/\{(\w+)\}/g, (match, key: string) => {
    const value = params[key];
    return value === undefined ? match : String(value);
  });
}

export function translate(locale: Locale, key: TranslationKey, params?: TranslationParams): string {
  const dictionary = dictionaries[locale] ?? dictionaries[DEFAULT_LOCALE];
  const fallback = dictionaries[DEFAULT_LOCALE];
  const template = dictionary[key] ?? fallback[key] ?? key;
  return interpolate(template, params);
}
