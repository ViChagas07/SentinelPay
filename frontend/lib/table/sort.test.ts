import { describe, expect, it } from "vitest";

import { sortRows, type SortableColumn } from "./sort";

type Row = {
  id: string;
  score: number;
};

const rows: Row[] = [
  { id: "doc_10", score: 42 },
  { id: "doc_2", score: 86 },
  { id: "doc_1", score: 18 },
];

const columns: SortableColumn<Row>[] = [
  { id: "id", sortValue: (row) => row.id },
  { id: "score", sortValue: (row) => row.score },
  { id: "plain" },
];

describe("sortRows", () => {
  it("returns a copy in the original order when there is no sort", () => {
    const result = sortRows(rows, columns, null);
    expect(result).toEqual(rows);
    expect(result).not.toBe(rows);
  });

  it("sorts numbers in both directions", () => {
    expect(
      sortRows(rows, columns, { columnId: "score", direction: "asc" }).map((row) => row.score),
    ).toEqual([18, 42, 86]);
    expect(
      sortRows(rows, columns, { columnId: "score", direction: "desc" }).map((row) => row.score),
    ).toEqual([86, 42, 18]);
  });

  it("sorts identifiers with numeric awareness", () => {
    expect(
      sortRows(rows, columns, { columnId: "id", direction: "asc" }).map((row) => row.id),
    ).toEqual(["doc_1", "doc_2", "doc_10"]);
  });

  it("ignores columns without a sort value and preserves stability", () => {
    expect(sortRows(rows, columns, { columnId: "plain", direction: "asc" })).toEqual(rows);
    expect(sortRows(rows, columns, { columnId: "missing", direction: "asc" })).toEqual(rows);
  });
});
