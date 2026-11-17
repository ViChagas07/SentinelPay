import { describe, expect, it } from "vitest";

import type { AnalysisListItem, AnalysisList } from "@/lib/api/schemas";

import {
  DEFAULT_LIBRARY_PARAMS,
  LIBRARY_MAX_QUERY_LENGTH,
  collectAnalysisPages,
  computeLibraryView,
  hasActiveLibraryFilters,
  libraryHref,
  matchesLibraryQuery,
  parseLibraryParams,
  periodStart,
  serializeLibraryParams,
  sortLibraryItems,
  statusGroupOf,
  type LibraryParams,
} from "./library";

const NOW = new Date("2026-11-16T15:00:00Z");

function analysis(
  id: string,
  createdAt: string,
  score: number | null,
  band: "low" | "attention" | "high" | null,
  status: AnalysisListItem["status"] = "completed",
  kind: AnalysisListItem["kind"] = "boleto",
): AnalysisListItem {
  return {
    id,
    status,
    kind,
    score,
    band,
    error_code: null,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function params(overrides: Partial<LibraryParams> = {}): LibraryParams {
  return { ...DEFAULT_LIBRARY_PARAMS, ...overrides };
}

const ITEMS: AnalysisListItem[] = [
  analysis("11111111-1111-4111-8111-111111111111", "2026-11-15T15:00:00Z", 12, "low"),
  analysis("22222222-2222-4222-8222-222222222222", "2026-11-13T15:00:00Z", 55, "attention"),
  analysis("33333333-3333-4333-8333-333333333333", "2026-11-06T15:00:00Z", 78, "high"),
  analysis("44444444-4444-4444-8444-444444444444", "2026-10-27T15:00:00Z", 32, "low"),
  analysis(
    "55555555-5555-4555-8555-555555555555",
    "2026-11-16T13:00:00Z",
    null,
    null,
    "processing",
  ),
  analysis("66666666-6666-4666-8666-666666666666", "2026-11-16T14:00:00Z", null, null, "failed"),
  analysis("77777777-7777-4777-8777-777777777777", "2026-10-12T15:00:00Z", 60, "attention"),
  analysis("88888888-8888-4888-8888-888888888888", "2026-10-07T15:00:00Z", 70, "high"),
  analysis("99999999-9999-4999-8999-999999999999", "2026-09-27T15:00:00Z", 80, "high"),
  analysis("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "2026-11-14T15:00:00Z", 18, "low", "degraded"),
  analysis(
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "2026-11-12T15:00:00Z",
    67,
    "attention",
    "completed",
    "payslip",
  ),
  analysis(
    "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "2026-11-11T15:00:00Z",
    91,
    "high",
    "completed",
    "payslip",
  ),
];

describe("parseLibraryParams", () => {
  it("returns the defaults for an empty query string", () => {
    expect(parseLibraryParams(new URLSearchParams())).toEqual(DEFAULT_LIBRARY_PARAMS);
  });

  it("reads valid values and ignores invalid ones", () => {
    const search = new URLSearchParams(
      "band=high&status=done&period=30&q=%23ABCD-1234&sort=score&dir=asc&page=3",
    );

    expect(parseLibraryParams(search)).toEqual({
      band: "high",
      status: "done",
      period: 30,
      query: "#ABCD-1234",
      sort: "score",
      direction: "asc",
      page: 3,
    });

    expect(
      parseLibraryParams(
        new URLSearchParams("band=unknown&status=none&period=12&sort=value&dir=up&page=0"),
      ),
    ).toEqual(DEFAULT_LIBRARY_PARAMS);
  });

  it("limits the search length", () => {
    const query = "a".repeat(LIBRARY_MAX_QUERY_LENGTH + 10);

    expect(parseLibraryParams(new URLSearchParams({ q: query })).query).toHaveLength(
      LIBRARY_MAX_QUERY_LENGTH,
    );
  });
});

describe("serializeLibraryParams and libraryHref", () => {
  it("omits every default value", () => {
    expect(serializeLibraryParams(DEFAULT_LIBRARY_PARAMS).toString()).toBe("");
    expect(libraryHref("/boletos", DEFAULT_LIBRARY_PARAMS)).toBe("/boletos");
  });

  it("round trips a non-default view", () => {
    const original = params({
      band: "attention",
      status: "active",
      period: 90,
      query: "abc",
      sort: "score",
      direction: "asc",
      page: 2,
    });

    expect(parseLibraryParams(serializeLibraryParams(original))).toEqual(original);
    expect(libraryHref("/folha", original)).toBe(
      "/folha?band=attention&status=active&period=90&q=abc&sort=score&dir=asc&page=2",
    );
  });

  it("detects active filters", () => {
    expect(hasActiveLibraryFilters(DEFAULT_LIBRARY_PARAMS)).toBe(false);
    expect(hasActiveLibraryFilters(params({ band: "low" }))).toBe(true);
    expect(hasActiveLibraryFilters(params({ query: "abc" }))).toBe(true);
    expect(hasActiveLibraryFilters(params({ page: 2 }))).toBe(false);
  });
});

describe("statusGroupOf", () => {
  it("groups the job statuses used by the filter", () => {
    expect(statusGroupOf("queued")).toBe("active");
    expect(statusGroupOf("running")).toBe("active");
    expect(statusGroupOf("processing")).toBe("active");
    expect(statusGroupOf("cancelling")).toBe("active");
    expect(statusGroupOf("completed")).toBe("done");
    expect(statusGroupOf("degraded")).toBe("done");
    expect(statusGroupOf("failed")).toBe("failed");
    expect(statusGroupOf("cancelled")).toBe("failed");
  });
});

describe("periodStart", () => {
  it("returns null for the entire period and the cutoff otherwise", () => {
    expect(periodStart("all", NOW)).toBeNull();
    expect(periodStart(7, NOW)?.toISOString()).toBe("2026-11-09T15:00:00.000Z");
    expect(periodStart(30, NOW)?.toISOString()).toBe("2026-10-17T15:00:00.000Z");
  });
});

describe("matchesLibraryQuery", () => {
  const item = ITEMS[0];

  it("matches the identifier with or without the hash and dashes", () => {
    expect(matchesLibraryQuery(item, "11111111")).toBe(true);
    expect(matchesLibraryQuery(item, "#11111111")).toBe(true);
    expect(matchesLibraryQuery(item, "1111-1111")).toBe(true);
    expect(matchesLibraryQuery(item, "99999999")).toBe(false);
  });

  it("treats an empty query as a match", () => {
    expect(matchesLibraryQuery(item, "   ")).toBe(true);
  });
});

describe("computeLibraryView", () => {
  it("counts classes over the whole filtered sample, not only the page", () => {
    const view = computeLibraryView(ITEMS, "boleto", params(), NOW, 2);

    expect(view.kindTotal).toBe(10);
    expect(view.counts).toEqual({ all: 10, low: 3, attention: 2, high: 3 });
    expect(view.total).toBe(10);
    expect(view.totalPages).toBe(5);
    expect(view.items).toHaveLength(2);
  });

  it("keeps class counts stable when a class tab filters the rows", () => {
    const view = computeLibraryView(ITEMS, "boleto", params({ band: "high" }), NOW);

    expect(view.counts).toEqual({ all: 10, low: 3, attention: 2, high: 3 });
    expect(view.total).toBe(3);
    expect(view.items.every((item) => item.band === "high")).toBe(true);
  });

  it("applies period, status and query before counting", () => {
    const view = computeLibraryView(
      ITEMS,
      "boleto",
      params({ period: 30, status: "done", query: "aaa" }),
      NOW,
    );

    expect(view.total).toBe(1);
    expect(view.counts.all).toBe(1);
    expect(view.counts.low).toBe(1);
    expect(view.items[0].id).toBe("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
  });

  it("counts queued and processing analyses only in the all tab", () => {
    const statuses = computeLibraryView(ITEMS, "boleto", params({ status: "active" }), NOW);

    expect(statuses.counts).toEqual({ all: 1, low: 0, attention: 0, high: 0 });
    expect(statuses.activeCount).toBe(1);
    expect(statuses.items[0].status).toBe("processing");
  });

  it("keeps only the requested kind", () => {
    const payslips = computeLibraryView(ITEMS, "payslip", params(), NOW);

    expect(payslips.kindTotal).toBe(2);
    expect(payslips.items.every((item) => item.kind === "payslip")).toBe(true);
  });

  it("clamps a page beyond the last valid page", () => {
    const view = computeLibraryView(ITEMS, "boleto", params({ page: 99 }), NOW, 4);

    expect(view.totalPages).toBe(3);
    expect(view.page).toBe(3);
    expect(view.items).toHaveLength(2);
  });
});

describe("sortLibraryItems", () => {
  it("sorts by date in both directions", () => {
    const descending = sortLibraryItems(ITEMS, "date", "desc");
    const ascending = sortLibraryItems(ITEMS, "date", "asc");

    expect(descending[0].created_at).toBe("2026-11-16T14:00:00Z");
    expect(ascending[0].created_at).toBe("2026-09-27T15:00:00Z");
  });

  it("sorts by score and always leaves null scores at the end", () => {
    const descending = sortLibraryItems(ITEMS, "score", "desc");
    const ascending = sortLibraryItems(ITEMS, "score", "asc");

    expect(descending[0].score).toBe(91);
    expect(descending.at(-1)?.score).toBeNull();
    expect(ascending[0].score).toBe(12);
    expect(ascending.at(-1)?.score).toBeNull();
  });
});

describe("collectAnalysisPages", () => {
  it("follows the cursor until the end", async () => {
    const cursors: (string | null)[] = [];
    const loadPage = async (cursor: string | null): Promise<AnalysisList> => {
      cursors.push(cursor);

      return cursor === null
        ? { items: [ITEMS[0]], next_cursor: "next" }
        : { items: [ITEMS[1]], next_cursor: null };
    };

    const dataset = await collectAnalysisPages(loadPage, {
      now: () => "2026-11-16T15:00:00.000Z",
    });

    expect(cursors).toEqual([null, "next"]);
    expect(dataset.items).toHaveLength(2);
    expect(dataset.truncated).toBe(false);
    expect(dataset.fetchedAt).toBe("2026-11-16T15:00:00.000Z");
  });

  it("marks the sample as truncated when the page limit is reached", async () => {
    const loadPage = async (): Promise<AnalysisList> => ({
      items: [ITEMS[0]],
      next_cursor: "more",
    });

    const dataset = await collectAnalysisPages(loadPage, { maxPages: 3 });

    expect(dataset.items).toHaveLength(3);
    expect(dataset.truncated).toBe(true);
  });

  it("stops when a page is empty even if a cursor is present", async () => {
    const loadPage = async (): Promise<AnalysisList> => ({
      items: [],
      next_cursor: "unexpected",
    });

    const dataset = await collectAnalysisPages(loadPage, { maxPages: 5 });

    expect(dataset.items).toHaveLength(0);
    expect(dataset.truncated).toBe(true);
  });
});
