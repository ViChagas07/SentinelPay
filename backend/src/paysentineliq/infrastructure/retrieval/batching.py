from collections.abc import Iterator
from typing import TypeVar

T = TypeVar("T")


def iter_batches(items: tuple[T, ...], size: int) -> Iterator[tuple[T, ...]]:
    if size <= 0:
        raise ValueError("batch size must be positive")
    for start in range(0, len(items), size):
        yield items[start : start + size]
