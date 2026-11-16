import { coerceDate, formatDate, INTL_LOCALE } from "@/lib/i18n/format";
import type { Locale } from "@/lib/i18n";

export const DATE_FORMAT_COOKIE = "date_format";

export const DATE_FORMATS = ["auto", "dmy", "mdy", "iso"] as const;

export type DateFormat = (typeof DATE_FORMATS)[number];

export const DEFAULT_DATE_FORMAT: DateFormat = "auto";

export function isDateFormat(value: string | undefined | null): value is DateFormat {
  return value === "auto" || value === "dmy" || value === "mdy" || value === "iso";
}

export function resolveDateFormat(value: string | undefined | null): DateFormat {
  return isDateFormat(value) ? value : DEFAULT_DATE_FORMAT;
}

const DATE_LOCALE: Record<Exclude<DateFormat, "auto">, string> = {
  dmy: "pt-BR",
  mdy: "en-US",
  iso: "sv-SE",
};

function timeOptions(style: Intl.DateTimeFormatOptions["timeStyle"]): Intl.DateTimeFormatOptions {
  switch (style) {
    case "short":
      return { hour: "2-digit", minute: "2-digit" };
    case "medium":
      return { hour: "2-digit", minute: "2-digit", second: "2-digit" };
    case "long":
      return { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZoneName: "short" };
    case "full":
      return { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZoneName: "long" };
    default:
      return {};
  }
}

export function formatDateWithPreference(
  value: Date | string | number,
  locale: Locale,
  dateFormat: DateFormat,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium" },
): string {
  if (dateFormat === "auto" || options.dateStyle === undefined) {
    return formatDate(value, locale, options);
  }

  const explicit: Intl.DateTimeFormatOptions = { ...options };
  const timeStyle = explicit.timeStyle;
  delete explicit.dateStyle;
  delete explicit.timeStyle;

  const date = coerceDate(value);
  const datePart = new Intl.DateTimeFormat(DATE_LOCALE[dateFormat], {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: explicit.timeZone,
  }).format(date);

  if (!timeStyle) {
    return datePart;
  }

  const timePart = new Intl.DateTimeFormat(INTL_LOCALE[locale], {
    ...timeOptions(timeStyle),
    timeZone: explicit.timeZone,
    hour12: explicit.hour12,
  }).format(date);

  return `${datePart}, ${timePart}`;
}
