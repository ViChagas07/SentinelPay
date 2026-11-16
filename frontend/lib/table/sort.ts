export type SortDirection = "asc" | "desc";

export type SortState = {
  columnId: string;
  direction: SortDirection;
} | null;

export type SortableColumn<T> = {
  id: string;
  sortValue?: (row: T) => string | number;
};

type DecoratedRow<T> = {
  row: T;
  index: number;
  value: string | number;
};

export function sortRows<T>(
  rows: readonly T[],
  columns: readonly SortableColumn<T>[],
  sort: SortState,
): T[] {
  if (sort === null) {
    return [...rows];
  }

  const column = columns.find((candidate) => candidate.id === sort.columnId);
  const sortValue = column?.sortValue;

  if (!sortValue) {
    return [...rows];
  }

  const direction = sort.direction === "asc" ? 1 : -1;
  const decorated: DecoratedRow<T>[] = rows.map((row, index) => ({
    row,
    index,
    value: sortValue(row),
  }));

  decorated.sort((left, right) => {
    if (typeof left.value === "number" && typeof right.value === "number") {
      return (left.value - right.value) * direction || left.index - right.index;
    }

    const comparison = String(left.value).localeCompare(String(right.value), undefined, {
      numeric: true,
      sensitivity: "base",
    });

    return comparison * direction || left.index - right.index;
  });

  return decorated.map((item) => item.row);
}
