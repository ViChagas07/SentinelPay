import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from paysentineliq.domain.boleto.dv import DvAlgorithm
from paysentineliq.domain.boleto.sources import MANUAL_FEBRABAN


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_marks.casefold().split())


@dataclass(frozen=True, slots=True)
class Bank:
    code: str
    name: str
    aliases: tuple[str, ...]
    field_dv: Mapping[int, DvAlgorithm]
    source: str

    def __post_init__(self) -> None:
        if len(self.code) != 3 or not self.code.isdigit():
            raise ValueError("bank code must have three digits")
        if not self.name.strip():
            raise ValueError("bank name is required")
        if not self.source.strip():
            raise ValueError("bank source is required")


class BankDirectory:
    def __init__(
        self,
        *,
        banks: tuple[Bank, ...],
        version: str,
        sources: tuple[str, ...],
    ) -> None:
        self._banks = tuple(banks)
        self._by_code = {bank.code: bank for bank in banks}
        self.version = version
        self.sources = tuple(sources)

    @property
    def banks(self) -> tuple[Bank, ...]:
        return self._banks

    def find_by_code(self, code: str) -> Bank | None:
        return self._by_code.get(code)

    def find_by_name(self, text: str) -> Bank | None:
        folded = _fold(text)
        candidates: list[tuple[int, Bank]] = []
        for bank in self._banks:
            for label in (bank.name, *bank.aliases):
                folded_label = _fold(label)
                if folded_label and folded_label in folded:
                    candidates.append((len(folded_label), bank))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1].code))
        return candidates[0][1]

    def field_dv_algorithm(self, bank_code: str, field: int) -> DvAlgorithm:
        bank = self._by_code.get(bank_code)
        if bank is None:
            return DvAlgorithm.MOD10
        return bank.field_dv.get(field, DvAlgorithm.MOD10)

    def field_dv_source(self, bank_code: str, field: int) -> str:
        bank = self._by_code.get(bank_code)
        if bank is not None and field in bank.field_dv:
            return bank.source
        return MANUAL_FEBRABAN


EMPTY_BANK_DIRECTORY = BankDirectory(banks=(), version="empty", sources=())
