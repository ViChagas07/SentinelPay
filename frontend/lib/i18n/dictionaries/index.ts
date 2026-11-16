import type { Locale } from "../constants";
import { en } from "./en";
import { es } from "./es";
import { pt, type Dictionary, type TranslationKey } from "./pt";

export { en, es, pt };
export type { Dictionary, TranslationKey };

export const dictionaries: Record<Locale, Dictionary> = {
  pt,
  es,
  en,
};
