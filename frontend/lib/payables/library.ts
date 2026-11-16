import type { Payable, PayableList, PayableStatus } from "@/lib/api/schemas";
import { getDueDateRelation } from "@/lib/dashboard/date";

export type PaymentsFilter = "open" | "all" | "paid" | "overdue";

export const PAYMENTS_FILTERS: readonly PaymentsFilter[] = ["open", "all", "paid", "overdue"];

export const PAYMENTS_PAGE_SIZE = 10;
export const PAYMENTS_API_PAGE_SIZE = 50;
export const PAYMENTS_MAX_PAGES = 10;
export const PAYMENTS_MAX_SAMPLE = PAYMENTS_API_PAGE_SIZE * PAYMENTS_MAX_PAGES;
export const TIMELINE_DAYS = 30;

export const ACTIVE_PAYABLE_STATUSES: readonly PayableStatus[] = [
  "pending_confirmation",
  "pending",
  "overdue",
];

export type PaymentSituation = "upcoming" | "today" | "overdue" | "paid" | "dismissed";

export type PaymentsSummary = {
  upcoming: number;
  today: number;
  overdue: number;
};

export type PayableSample = {
  items: Payable[];
  truncated: boolean;
  fetchedAt: string;
};

export type PayableTimelineGroup = {
  date: string;
  dayOffset: number;
  count: number;
  totalCents: number;
  payableIds: string[];
};

export type PayablePage = {
  items: Payable[];
  page: number;
  totalPages: number;
  total: number;
};

export function statusesForFilter(filter: PaymentsFilter): PayableStatus[] | null {
  switch (filter) {
    case "open":
      return [...ACTIVE_PAYABLE_STATUSES];
    case "paid":
      return ["paid"];
    case "overdue":
      return ["overdue"];
    case "all":
      return null;
  }
}

export function payableSituation(
  payable: Payable,
  timeZone: string,
  now: Date = new Date(),
): PaymentSituation {
  if (payable.status === "paid") {
    return "paid";
  }

  if (payable.status === "dismissed") {
    return "dismissed";
  }

  if (payable.status === "overdue") {
    return "overdue";
  }

  const relation = getDueDateRelation(payable.due_date, timeZone, now);

  if (relation === null) {
    return "upcoming";
  }

  if (relation.kind === "today") {
    return "today";
  }

  if (relation.kind === "yesterday" || relation.kind === "daysAgo") {
    return "overdue";
  }

  return "upcoming";
}

export function isActivePayable(payable: Payable): boolean {
  return (
    payable.status === "pending" ||
    payable.status === "pending_confirmation" ||
    payable.status === "overdue"
  );
}

export function summarizeActivePayables(
  payables: readonly Payable[],
  timeZone: string,
  now: Date = new Date(),
): PaymentsSummary {
  return payables.reduce<PaymentsSummary>(
    (summary, payable) => {
      if (!isActivePayable(payable)) {
        return summary;
      }

      const situation = payableSituation(payable, timeZone, now);

      if (situation === "today") {
        summary.today += 1;
      } else if (situation === "overdue") {
        summary.overdue += 1;
      } else {
        summary.upcoming += 1;
      }

      return summary;
    },
    { upcoming: 0, today: 0, overdue: 0 },
  );
}

export function sortPayables(payables: readonly Payable[]): Payable[] {
  return [...payables].sort(
    (left, right) => left.due_date.localeCompare(right.due_date) || left.id.localeCompare(right.id),
  );
}

export function amountToCents(amount: string): number {
  const value = Number(amount);

  return Number.isFinite(value) ? Math.round(value * 100) : 0;
}

export function buildPayableTimeline(
  payables: readonly Payable[],
  timeZone: string,
  now: Date = new Date(),
  days: number = TIMELINE_DAYS,
): PayableTimelineGroup[] {
  const safeDays = Math.max(1, Math.trunc(days));
  const groups = new Map<string, PayableTimelineGroup>();

  for (const payable of payables) {
    if (!isActivePayable(payable)) {
      continue;
    }

    const relation = getDueDateRelation(payable.due_date, timeZone, now);

    if (
      relation === null ||
      relation.kind === "yesterday" ||
      relation.kind === "daysAgo" ||
      relation.days > safeDays
    ) {
      continue;
    }

    const current = groups.get(payable.due_date) ?? {
      date: payable.due_date,
      dayOffset: relation.days,
      count: 0,
      totalCents: 0,
      payableIds: [],
    };

    current.count += 1;
    current.totalCents += amountToCents(payable.amount);
    current.payableIds.push(payable.id);
    groups.set(payable.due_date, current);
  }

  return [...groups.values()].sort((left, right) => left.date.localeCompare(right.date));
}

export function paginatePayables(
  payables: readonly Payable[],
  page: number,
  pageSize: number = PAYMENTS_PAGE_SIZE,
): PayablePage {
  const safePageSize = Math.max(1, Math.trunc(pageSize));
  const total = payables.length;
  const totalPages = Math.max(1, Math.ceil(total / safePageSize));
  const safePage = Math.min(Math.max(1, Math.trunc(page)), totalPages);
  const start = (safePage - 1) * safePageSize;

  return {
    items: payables.slice(start, start + safePageSize),
    page: safePage,
    totalPages,
    total,
  };
}

export function filterPayables(
  payables: readonly Payable[],
  situation: PaymentsFilter,
  timeZone: string,
  now: Date = new Date(),
): Payable[] {
  if (situation === "all") {
    return [...payables];
  }

  if (situation === "paid") {
    return payables.filter((payable) => payable.status === "paid");
  }

  if (situation === "overdue") {
    return payables.filter((payable) => payableSituation(payable, timeZone, now) === "overdue");
  }

  return payables.filter((payable) => isActivePayable(payable));
}

export async function collectPayablePages(
  loadPage: (cursor: string | null) => Promise<PayableList>,
  options: { maxPages?: number; now?: () => string } = {},
): Promise<PayableSample> {
  const maxPages = Math.max(1, Math.trunc(options.maxPages ?? PAYMENTS_MAX_PAGES));
  const items: Payable[] = [];
  let cursor: string | null = null;
  let pages = 0;

  while (pages < maxPages) {
    const page = await loadPage(cursor);

    items.push(...page.items);
    pages += 1;

    if (page.next_cursor === null || page.items.length === 0) {
      cursor = page.next_cursor;
      break;
    }

    cursor = page.next_cursor;
  }

  return {
    items,
    truncated: cursor !== null,
    fetchedAt: options.now ? options.now() : new Date().toISOString(),
  };
}
