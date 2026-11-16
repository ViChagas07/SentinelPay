import { INTL_LOCALE, formatDate } from "@/lib/i18n/format";
import type { Locale } from "@/lib/i18n/constants";

export const DEFAULT_TIME_ZONE = "UTC";

const DAY_MS = 86_400_000;

export type DueDateRelation =
  | { kind: "today"; days: 0 }
  | { kind: "tomorrow"; days: 1 }
  | { kind: "inDays"; days: number }
  | { kind: "yesterday"; days: -1 }
  | { kind: "daysAgo"; days: number };

function parseDateKey(key: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(key);

  if (!match) {
    return null;
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);

  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
    return null;
  }

  return Date.UTC(year, month - 1, day);
}

function keyFromUtcTimestamp(timestamp: number): string {
  return new Date(timestamp).toISOString().slice(0, 10);
}

export function resolveTimeZone(
  timeZone: string | null | undefined,
  fallback: string = DEFAULT_TIME_ZONE,
): string {
  if (!timeZone) {
    return fallback;
  }

  try {
    new Intl.DateTimeFormat("en-US", { timeZone }).format(new Date());
    return timeZone;
  } catch {
    return fallback;
  }
}

export function dateKeyInTimeZone(value: Date | string, timeZone: string): string {
  const date = value instanceof Date ? value : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: resolveTimeZone(timeZone),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);

  const year = parts.find((part) => part.type === "year")?.value ?? "";
  const month = parts.find((part) => part.type === "month")?.value ?? "";
  const day = parts.find((part) => part.type === "day")?.value ?? "";

  return `${year}-${month}-${day}`;
}

export function dateKeysForPeriod(periodDays: number, now: Date, timeZone: string): string[] {
  const todayKey = dateKeyInTimeZone(now, timeZone);
  const todayTimestamp = parseDateKey(todayKey);

  if (todayTimestamp === null) {
    return [];
  }

  const safeDays = Math.max(1, Math.floor(periodDays));

  return Array.from({ length: safeDays }, (_, index) =>
    keyFromUtcTimestamp(todayTimestamp - (safeDays - 1 - index) * DAY_MS),
  );
}

export function dateKeysFromToday(days: number, now: Date, timeZone: string): string[] {
  const todayKey = dateKeyInTimeZone(now, timeZone);
  const todayTimestamp = parseDateKey(todayKey);

  if (todayTimestamp === null) {
    return [];
  }

  const safeDays = Math.max(1, Math.floor(days));

  return Array.from({ length: safeDays }, (_, index) =>
    keyFromUtcTimestamp(todayTimestamp + index * DAY_MS),
  );
}

export function daysBetweenDateKeys(fromKey: string, toKey: string): number | null {
  const from = parseDateKey(fromKey);
  const to = parseDateKey(toKey);

  if (from === null || to === null) {
    return null;
  }

  return Math.round((to - from) / DAY_MS);
}

export function getDueDateRelation(
  dueDate: string,
  timeZone: string,
  now: Date = new Date(),
): DueDateRelation | null {
  const todayKey = dateKeyInTimeZone(now, timeZone);
  const difference = daysBetweenDateKeys(todayKey, dueDate);

  if (difference === null) {
    return null;
  }

  if (difference === 0) {
    return { kind: "today", days: 0 };
  }

  if (difference === 1) {
    return { kind: "tomorrow", days: 1 };
  }

  if (difference > 1) {
    return { kind: "inDays", days: difference };
  }

  if (difference === -1) {
    return { kind: "yesterday", days: -1 };
  }

  return { kind: "daysAgo", days: Math.abs(difference) };
}

export function formatDashboardDate(now: Date, locale: Locale, timeZone: string): string {
  return formatDate(now, locale, {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
    timeZone: resolveTimeZone(timeZone),
  });
}

export function formatRelativeTime(value: string, locale: Locale, now: Date = new Date()): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = diffMs / 60_000;
  const relative = new Intl.RelativeTimeFormat(INTL_LOCALE[locale], { numeric: "auto" });

  if (Math.abs(diffMs) < 60_000) {
    return relative.format(0, "second");
  }

  if (Math.abs(diffMinutes) < 60) {
    return relative.format(-Math.round(diffMinutes), "minute");
  }

  const diffHours = diffMinutes / 60;

  if (Math.abs(diffHours) < 24) {
    return relative.format(-Math.round(diffHours), "hour");
  }

  const diffDays = diffHours / 24;

  if (Math.abs(diffDays) < 7) {
    return relative.format(-Math.round(diffDays), "day");
  }

  const diffWeeks = diffDays / 7;

  if (Math.abs(diffWeeks) < 5) {
    return relative.format(-Math.round(diffWeeks), "week");
  }

  const diffMonths = diffDays / 30;

  if (Math.abs(diffMonths) < 12) {
    return relative.format(-Math.round(diffMonths), "month");
  }

  return relative.format(-Math.round(diffDays / 365), "year");
}

export function formatSignedPoints(value: number, locale: Locale): string {
  return new Intl.NumberFormat(INTL_LOCALE[locale], {
    signDisplay: "exceptZero",
    maximumFractionDigits: 0,
  }).format(value);
}
