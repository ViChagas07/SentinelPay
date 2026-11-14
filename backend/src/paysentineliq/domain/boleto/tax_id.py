from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from paysentineliq.domain.boleto.digits import only_digits

_ASCII_DIGITS = frozenset("0123456789")


class TaxIdKind(StrEnum):
    CPF = "cpf"
    CNPJ = "cnpj"


def _validate_tax_id_digits(digits: str, length: int) -> None:
    if len(digits) != length or any(char not in _ASCII_DIGITS for char in digits):
        raise ValueError(f"tax id must have exactly {length} digits")


def _cpf_check_digit(data: str, weights: range) -> int:
    total = sum(int(char) * weight for char, weight in zip(data, weights, strict=True))
    remainder = (total * 10) % 11
    return 0 if remainder == 10 else remainder


def _cnpj_check_digit(data: str, weights: tuple[int, ...]) -> int:
    total = sum(int(char) * weight for char, weight in zip(data, weights, strict=True))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


@dataclass(frozen=True, slots=True)
class Cpf:
    digits: str

    def __post_init__(self) -> None:
        _validate_tax_id_digits(self.digits, 11)

    @property
    def kind(self) -> TaxIdKind:
        return TaxIdKind.CPF

    @property
    def is_valid(self) -> bool:
        if len(set(self.digits)) == 1:
            return False
        first = _cpf_check_digit(self.digits[:9], range(10, 1, -1))
        second = _cpf_check_digit(self.digits[:10], range(11, 1, -1))
        return self.digits[9:] == f"{first}{second}"

    @property
    def masked(self) -> str:
        return f"***.***.***-{self.digits[-2:]}"


@dataclass(frozen=True, slots=True)
class Cnpj:
    digits: str

    def __post_init__(self) -> None:
        _validate_tax_id_digits(self.digits, 14)

    @property
    def kind(self) -> TaxIdKind:
        return TaxIdKind.CNPJ

    @property
    def is_valid(self) -> bool:
        if not any(char != "0" for char in self.digits):
            return False
        first = _cnpj_check_digit(
            self.digits[:12],
            (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
        )
        second = _cnpj_check_digit(
            self.digits[:13],
            (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
        )
        return self.digits[12:] == f"{first}{second}"

    @property
    def masked(self) -> str:
        return f"**.***.***/****-{self.digits[-2:]}"


TaxId: TypeAlias = Cpf | Cnpj


def parse_tax_id(text: str) -> TaxId | None:
    digits = only_digits(text)
    if len(digits) == 11:
        return Cpf(digits)
    if len(digits) == 14:
        return Cnpj(digits)
    return None
