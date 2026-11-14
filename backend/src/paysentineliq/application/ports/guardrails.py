from typing import Protocol


class GuardrailMetricsPort(Protocol):
    def record(self, layer: str, code: str) -> None: ...


class InjectionClassifierPort(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def model_version(self) -> str: ...

    def score(self, text: str) -> float: ...
