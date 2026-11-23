import type { Locale } from "@/lib/i18n/constants";

import { en } from "./en";
import { es } from "./es";
import { pt } from "./pt";
import type { LegalContent } from "./types";

export const legalContent: Record<Locale, LegalContent> = {
  pt,
  es,
  en,
};

export type { LegalBlock, LegalContent, LegalDocument, LegalSection } from "./types";
