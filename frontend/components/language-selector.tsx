"use client";

import { Languages } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LOCALES, isLocale, type Locale } from "@/lib/i18n";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";

const LOCALE_LABEL_KEYS: Record<Locale, TranslationKey> = {
  pt: "language.pt",
  es: "language.es",
  en: "language.en",
};

const LOCALE_SHORT_LABELS: Record<Locale, string> = {
  pt: "PT",
  es: "ES",
  en: "EN",
};

export function LanguageSelector() {
  const { t, locale, setLocale } = useI18n();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm">
          <Languages aria-hidden="true" />
          <span className="sr-only">
            {t("language.label")}: {t(LOCALE_LABEL_KEYS[locale])}
          </span>
          <span className="font-mono text-xs tracking-widest">{LOCALE_SHORT_LABELS[locale]}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>{t("language.label")}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuRadioGroup
          value={locale}
          onValueChange={(value) => {
            if (isLocale(value)) {
              setLocale(value);
            }
          }}
        >
          {LOCALES.map((option) => (
            <DropdownMenuRadioItem key={option} value={option}>
              {t(LOCALE_LABEL_KEYS[option])}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
