import { describe, expect, it } from "vitest";

import type { Payable, PayableList, PayableStatus } from "@/lib/api/schemas";

import {
  ACTIVE_PAYABLE_STATUSES,
  amountToCents,
  buildPayableTimeline,
  collectPayablePages,
  filterPayables,
  paginatePayables,
  payableSituation,
  sortPayables,
  statusesForFilter,
  summarizeActivePayables,
} from "./library";

const NOW = new Date("2026-11-16T15:00:00Z");

function payable(id: string, dueDate: string, status: PayableStatus, amount = "100.00"): Payable {
  return {
    id,
    analysis_id: "11111111-1111-4111-8111-111111111111",
    description: `Conta ${id}`,
    amount,
    due_date: dueDate,
    status,
    created_at: "2026-11-01T12:00:00Z",
    updated_at: "2026-11-01T12:00:00Z",
  };
}

describe("statusesForFilter", () => {
  it("maps the display filter to real API status filters", () => {
    expect(statusesForFilter("open")).toEqual([...ACTIVE_PAYABLE_STATUSES]);
    expect(statusesForFilter("paid")).toEqual(["paid"]);
    expect(statusesForFilter("overdue")).toEqual(["overdue"]);
    expect(statusesForFilter("all")).toBeNull();
  });
});

describe("payableSituation", () => {
  it("keeps terminal statuses and derives the active situation from the due date", () => {
    expect(payableSituation(payable("1", "2026-11-10", "paid"), "UTC", NOW)).toBe("paid");
    expect(payableSituation(payable("2", "2026-11-10", "dismissed"), "UTC", NOW)).toBe("dismissed");
    expect(payableSituation(payable("3", "2026-11-10", "overdue"), "UTC", NOW)).toBe("overdue");
    expect(payableSituation(payable("4", "2026-11-16", "pending"), "UTC", NOW)).toBe("today");
    expect(payableSituation(payable("5", "2026-11-14", "pending"), "UTC", NOW)).toBe("overdue");
    expect(payableSituation(payable("6", "2026-11-20", "pending_confirmation"), "UTC", NOW)).toBe(
      "upcoming",
    );
  });
});

describe("summarizeActivePayables", () => {
  it("counts upcoming, today and overdue without paid or dismissed", () => {
    const summary = summarizeActivePayables(
      [
        payable("1", "2026-11-20", "pending"),
        payable("2", "2026-11-22", "pending_confirmation"),
        payable("3", "2026-11-16", "pending"),
        payable("4", "2026-11-10", "pending"),
        payable("5", "2026-11-10", "overdue"),
        payable("6", "2026-11-10", "paid"),
        payable("7", "2026-11-10", "dismissed"),
      ],
      "UTC",
      NOW,
    );

    expect(summary).toEqual({ upcoming: 2, today: 1, overdue: 2 });
  });
});

describe("sortPayables", () => {
  it("orders by due date and breaks ties by id", () => {
    const sorted = sortPayables([
      payable("b", "2026-11-20", "pending"),
      payable("a", "2026-11-20", "pending"),
      payable("c", "2026-11-10", "overdue"),
    ]);

    expect(sorted.map((item) => item.id)).toEqual(["c", "a", "b"]);
  });
});

describe("amountToCents", () => {
  it("parses the decimal string returned by the API", () => {
    expect(amountToCents("123.45")).toBe(12345);
    expect(amountToCents("0.09")).toBe(9);
    expect(amountToCents("invalid")).toBe(0);
  });
});

describe("buildPayableTimeline", () => {
  it("groups active payables inside the window by date", () => {
    const groups = buildPayableTimeline(
      [
        payable("1", "2026-11-16", "pending", "100.00"),
        payable("2", "2026-11-16", "pending_confirmation", "50.00"),
        payable("3", "2026-11-20", "pending", "30.00"),
        payable("4", "2026-11-10", "overdue", "10.00"),
        payable("5", "2026-12-30", "pending", "99.00"),
        payable("6", "2026-11-20", "paid", "40.00"),
      ],
      "UTC",
      NOW,
      30,
    );

    expect(groups).toHaveLength(2);
    expect(groups[0]).toMatchObject({
      date: "2026-11-16",
      dayOffset: 0,
      count: 2,
      totalCents: 15000,
    });
    expect(groups[1]).toMatchObject({
      date: "2026-11-20",
      dayOffset: 4,
      count: 1,
      totalCents: 3000,
    });
  });

  it("returns an empty timeline when nothing is due in the window", () => {
    expect(buildPayableTimeline([payable("1", "2026-11-10", "overdue")], "UTC", NOW, 30)).toEqual(
      [],
    );
  });
});

describe("paginatePayables", () => {
  it("paginates and clamps the page", () => {
    const items = Array.from({ length: 23 }, (_, index) =>
      payable(String(index), "2026-11-20", "pending"),
    );

    const first = paginatePayables(items, 1, 10);
    expect(first.items).toHaveLength(10);
    expect(first.totalPages).toBe(3);

    const clamped = paginatePayables(items, 99, 10);
    expect(clamped.page).toBe(3);
    expect(clamped.items).toHaveLength(3);
  });
});

describe("filterPayables", () => {
  const items = [
    payable("1", "2026-11-20", "pending"),
    payable("2", "2026-11-10", "overdue"),
    payable("3", "2026-11-10", "paid"),
    payable("4", "2026-11-10", "dismissed"),
  ];

  it("filters the open, paid, overdue and all views", () => {
    expect(filterPayables(items, "open", "UTC", NOW).map((item) => item.id)).toEqual(["1", "2"]);
    expect(filterPayables(items, "paid", "UTC", NOW).map((item) => item.id)).toEqual(["3"]);
    expect(filterPayables(items, "overdue", "UTC", NOW).map((item) => item.id)).toEqual(["2"]);
    expect(filterPayables(items, "all", "UTC", NOW)).toHaveLength(4);
  });
});

describe("collectPayablePages", () => {
  it("follows the cursor and reports truncation", async () => {
    const loadPage = async (cursor: string | null): Promise<PayableList> => ({
      items: [payable(cursor ?? "first", "2026-11-20", "pending")],
      next_cursor: cursor === null ? "next" : null,
    });

    const sample = await collectPayablePages(loadPage, {
      now: () => "2026-11-16T15:00:00.000Z",
    });

    expect(sample.items).toHaveLength(2);
    expect(sample.truncated).toBe(false);
    expect(sample.fetchedAt).toBe("2026-11-16T15:00:00.000Z");
  });

  it("marks the sample as truncated at the page limit", async () => {
    const loadPage = async (): Promise<PayableList> => ({
      items: [payable("1", "2026-11-20", "pending")],
      next_cursor: "more",
    });

    const sample = await collectPayablePages(loadPage, { maxPages: 3 });
    expect(sample.items).toHaveLength(3);
    expect(sample.truncated).toBe(true);
  });
});
