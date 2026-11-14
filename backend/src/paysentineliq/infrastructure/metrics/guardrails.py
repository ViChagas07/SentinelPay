from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class GuardrailMetricEntry:
    layer: str
    code: str
    count: int


class InMemoryGuardrailMetrics:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], int] = {}
        self._lock = Lock()

    def record(self, layer: str, code: str) -> None:
        if not layer.strip() or not code.strip():
            raise ValueError("layer and code are required")
        with self._lock:
            key = (layer, code)
            self._counts[key] = self._counts.get(key, 0) + 1

    def snapshot(self) -> tuple[GuardrailMetricEntry, ...]:
        with self._lock:
            items = tuple(
                GuardrailMetricEntry(layer=layer, code=code, count=count)
                for (layer, code), count in sorted(self._counts.items())
            )
        return items

    @property
    def total(self) -> int:
        with self._lock:
            return sum(self._counts.values())
