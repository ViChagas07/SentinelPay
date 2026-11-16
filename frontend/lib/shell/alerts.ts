import type { NotificationList } from "@/lib/api/schemas";

export type AlertPage = Pick<NotificationList, "items" | "next_cursor">;

export type HighRiskAlertCount = {
  count: number;
  truncated: boolean;
};

export const ALERT_PAGE_SIZE = 50;
export const MAX_ALERT_PAGES = 10;

export async function countHighRiskAlerts(
  fetchPage: (cursor: string | null) => Promise<AlertPage>,
  maxPages: number = MAX_ALERT_PAGES,
): Promise<HighRiskAlertCount> {
  const pageLimit = Math.max(1, Math.floor(maxPages));
  let cursor: string | null = null;
  let count = 0;
  let pages = 0;

  do {
    const page = await fetchPage(cursor);
    count += page.items.length;
    cursor = page.next_cursor;
    pages += 1;
  } while (cursor !== null && pages < pageLimit);

  return { count, truncated: cursor !== null };
}

export function formatBadgeCount(count: number): string | null {
  if (!Number.isFinite(count) || count <= 0) {
    return null;
  }

  return count > 99 ? "99+" : String(Math.floor(count));
}

export function buildAlertTitle(options: {
  count: number;
  truncated: boolean;
  baseTitle: string;
  appName: string;
}): string {
  const suffix = `${options.baseTitle} | ${options.appName}`;

  if (options.count <= 0) {
    return suffix;
  }

  const value = options.truncated ? `${options.count}+` : String(options.count);
  return `(${value}) ${suffix}`;
}

export function alertIconHref(count: number): string {
  return count > 0 ? "/favicon-alert.svg" : "/icon.svg";
}
