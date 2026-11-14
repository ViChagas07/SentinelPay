import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from paysentineliq.domain.boleto.dv import DvAlgorithm
from paysentineliq.domain.boleto.sources import MANUAL_FEBRABAN

_DEFAULT_DATA_PATH = Path(__file__).with_name("data") / "febraban_banks_v1.json"


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


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return tuple(value)


def _field_dv(value: object, code: str) -> dict[int, DvAlgorithm]:
    if not isinstance(value, dict):
        raise ValueError(f"field_dv for bank {code} must be an object")
    result: dict[int, DvAlgorithm] = {}
    for field, algorithm in value.items():
        if not isinstance(field, str) or not field.isdigit():
            raise ValueError(f"field_dv key for bank {code} must be a digit")
        if not isinstance(algorithm, str):
            raise ValueError(f"field_dv value for bank {code} must be a string")
        result[int(field)] = DvAlgorithm(algorithm)
    return result


def load_bank_directory(path: Path | None = None) -> BankDirectory:
    source_path = path or _DEFAULT_DATA_PATH
    payload: object = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("bank data must be an object")

    version = payload.get("version")
    if not isinstance(version, str):
        raise ValueError("bank data version is required")
    sources = _string_tuple(payload.get("sources"), "sources")

    raw_banks = payload.get("banks")
    if not isinstance(raw_banks, list):
        raise ValueError("banks must be a list")

    banks: list[Bank] = []
    for raw_bank in raw_banks:
        if not isinstance(raw_bank, dict):
            raise ValueError("bank must be an object")
        code = raw_bank.get("code")
        name = raw_bank.get("name")
        source = raw_bank.get("source")
        if not isinstance(code, str) or not isinstance(name, str) or not isinstance(source, str):
            raise ValueError("bank code, name and source are required")
        banks.append(
            Bank(
                code=code,
                name=name,
                aliases=_string_tuple(raw_bank.get("aliases"), f"aliases for bank {code}"),
                field_dv=_field_dv(raw_bank.get("field_dv"), code),
                source=source,
            ),
        )

    return BankDirectory(banks=tuple(banks), version=version, sources=sources)


EMPTY_BANK_DIRECTORY = BankDirectory(banks=(), version="empty", sources=())
