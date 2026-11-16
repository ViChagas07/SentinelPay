"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Info, Monitor, Moon, Sun } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { useId } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { accountPreferencesSchema, type AccountPreferencesValues } from "@/lib/account/preferences";
import { DATE_FORMATS, isDateFormat, type DateFormat } from "@/lib/preferences/date-format";
import { isLocale, LOCALES, type Locale } from "@/lib/i18n";
import type { TranslationKey } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n/provider";
import { isThemeMode, THEME_MODES, type ThemeMode } from "@/lib/theme/constants";
import { useTheme } from "@/lib/theme/provider";

const LANGUAGE_KEYS: Record<Locale, TranslationKey> = {
  pt: "language.pt",
  es: "language.es",
  en: "language.en",
};

const THEME_KEYS: Record<ThemeMode, TranslationKey> = {
  system: "theme.system",
  light: "theme.light",
  dark: "theme.dark",
};

const THEME_ICONS = {
  system: Monitor,
  light: Sun,
  dark: Moon,
} as const;

const DATE_FORMAT_KEYS: Record<DateFormat, TranslationKey> = {
  auto: "account.preferences.dateAuto",
  dmy: "account.preferences.dateDmy",
  mdy: "account.preferences.dateMdy",
  iso: "account.preferences.dateIso",
};

export function PreferencesSection() {
  const { t, locale, setLocale, dateFormat, setDateFormat, formatDate } = useI18n();
  const { mode, setMode } = useTheme();
  const languageLabelId = useId();
  const themeLabelId = useId();
  const dateLabelId = useId();
  const form = useForm<AccountPreferencesValues>({
    resolver: zodResolver(accountPreferencesSchema),
    defaultValues: {
      locale,
      theme: mode,
      dateFormat,
    },
    mode: "onChange",
  });
  const preview = formatDate("2026-11-16T12:00:00Z", { dateStyle: "long" });

  return (
    <section aria-labelledby="account-preferences-title">
      <h2
        id="account-preferences-title"
        className="font-serif text-2xl leading-tight tracking-tight sm:text-3xl"
      >
        {t("account.preferences.title")}
      </h2>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-foreground/70">
        {t("account.preferences.description")}
      </p>

      <form
        className="mt-5 space-y-5 rounded-[6px] border border-border bg-card p-5 sm:p-6"
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <span
              id={languageLabelId}
              className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70"
            >
              {t("account.preferences.language")}
            </span>
            <Controller
              control={form.control}
              name="locale"
              render={({ field }) => (
                <Select
                  value={field.value}
                  onValueChange={(value) => {
                    if (isLocale(value)) {
                      field.onChange(value);
                      setLocale(value);
                    }
                  }}
                >
                  <SelectTrigger aria-labelledby={languageLabelId}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LOCALES.map((option) => (
                      <SelectItem key={option} value={option}>
                        {t(LANGUAGE_KEYS[option])}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            <p className="text-[0.65rem] leading-relaxed text-foreground/70">
              {t("account.preferences.languageHint")}
            </p>
          </div>

          <div className="space-y-1.5">
            <span
              id={themeLabelId}
              className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70"
            >
              {t("account.preferences.theme")}
            </span>
            <Controller
              control={form.control}
              name="theme"
              render={({ field }) => (
                <Select
                  value={field.value}
                  onValueChange={(value) => {
                    if (isThemeMode(value)) {
                      field.onChange(value);
                      setMode(value);
                    }
                  }}
                >
                  <SelectTrigger aria-labelledby={themeLabelId}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {THEME_MODES.map((option) => {
                      const Icon = THEME_ICONS[option];

                      return (
                        <SelectItem key={option} value={option}>
                          <span className="inline-flex items-center gap-2">
                            <Icon className="size-3.5" aria-hidden="true" />
                            {t(THEME_KEYS[option])}
                          </span>
                        </SelectItem>
                      );
                    })}
                  </SelectContent>
                </Select>
              )}
            />
            <p className="text-[0.65rem] leading-relaxed text-foreground/70">
              {t("account.preferences.themeHint")}
            </p>
          </div>

          <div className="space-y-1.5">
            <span
              id={dateLabelId}
              className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-foreground/70"
            >
              {t("account.preferences.dateFormat")}
            </span>
            <Controller
              control={form.control}
              name="dateFormat"
              render={({ field }) => (
                <Select
                  value={field.value}
                  onValueChange={(value) => {
                    if (isDateFormat(value)) {
                      field.onChange(value);
                      setDateFormat(value);
                    }
                  }}
                >
                  <SelectTrigger aria-labelledby={dateLabelId}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DATE_FORMATS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {t(DATE_FORMAT_KEYS[option])}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            <p className="text-[0.65rem] leading-relaxed text-foreground/70">
              {t("account.preferences.dateFormatHint")}
            </p>
          </div>
        </div>

        <p
          aria-live="polite"
          className="rounded-[6px] border border-border bg-surface px-3 py-2 font-mono text-xs text-foreground/70"
        >
          {t("account.preferences.example", { date: preview })}
        </p>

        <div className="flex items-start gap-2 border-t border-border pt-4 text-[0.65rem] leading-relaxed text-foreground/70">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <p>
            {t("account.preferences.applied")} {t("account.preferences.cookieNote")}
          </p>
        </div>
      </form>
    </section>
  );
}
