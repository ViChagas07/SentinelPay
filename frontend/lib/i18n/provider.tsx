"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { setApiLocale } from "@/lib/api/locale";
import { writeCookie } from "@/lib/cookies";
import {
  DATE_FORMAT_COOKIE,
  DEFAULT_DATE_FORMAT,
  formatDateWithPreference,
  type DateFormat,
} from "@/lib/preferences/date-format";

import { HTML_LANG, LOCALE_COOKIE, type Locale } from "./constants";
import type { TranslationKey } from "./dictionaries";
import { formatCurrency, formatNumber } from "./format";
import { translate, type TranslationParams } from "./translate";

type I18nContextValue = {
  locale: Locale;
  dateFormat: DateFormat;
  setDateFormat: (dateFormat: DateFormat) => void;
  t: (key: TranslationKey, params?: TranslationParams) => string;
  setLocale: (locale: Locale) => void;
  formatDate: (value: Date | string | number, options?: Intl.DateTimeFormatOptions) => string;
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string;
  formatCurrency: (value: number, currency?: string) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({
  initialLocale,
  initialDateFormat = DEFAULT_DATE_FORMAT,
  children,
}: Readonly<{
  initialLocale: Locale;
  initialDateFormat?: DateFormat;
  children: ReactNode;
}>) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const [dateFormat, setDateFormatState] = useState<DateFormat>(initialDateFormat);
  const router = useRouter();

  useEffect(() => {
    setApiLocale(HTML_LANG[locale]);
    document.documentElement.lang = HTML_LANG[locale];
  }, [locale]);

  const setLocale = useCallback(
    (nextLocale: Locale) => {
      writeCookie(LOCALE_COOKIE, nextLocale);
      setLocaleState(nextLocale);
      setApiLocale(HTML_LANG[nextLocale]);
      document.documentElement.lang = HTML_LANG[nextLocale];
      router.refresh();
    },
    [router],
  );

  const setDateFormat = useCallback((nextFormat: DateFormat) => {
    writeCookie(DATE_FORMAT_COOKIE, nextFormat);
    setDateFormatState(nextFormat);
  }, []);

  const t = useCallback(
    (key: TranslationKey, params?: TranslationParams) => translate(locale, key, params),
    [locale],
  );

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      dateFormat,
      setDateFormat,
      t,
      setLocale,
      formatDate: (date, options) => formatDateWithPreference(date, locale, dateFormat, options),
      formatNumber: (number, options) => formatNumber(number, locale, options),
      formatCurrency: (amount, currency) => formatCurrency(amount, locale, currency),
    }),
    [dateFormat, locale, setDateFormat, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);

  if (context === null) {
    throw new Error("useI18n must be used within I18nProvider");
  }

  return context;
}
