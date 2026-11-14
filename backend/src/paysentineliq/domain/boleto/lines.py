from dataclasses import dataclass

from paysentineliq.domain.boleto.bank_directory import BankDirectory
from paysentineliq.domain.boleto.digits import mod10, mod11
from paysentineliq.domain.boleto.dv import DvAlgorithm, DvError
from paysentineliq.domain.boleto.errors import NotVerifiableLayoutError
from paysentineliq.domain.boleto.sources import MANUAL_FEBRABAN

_ASCII_DIGITS = frozenset("0123456789")


def _validate_digits(digits: str, length: int, label: str) -> None:
    if len(digits) != length or any(char not in _ASCII_DIGITS for char in digits):
        raise ValueError(f"{label} must have exactly {length} digits")


@dataclass(frozen=True, slots=True)
class Barcode:
    digits: str

    def __post_init__(self) -> None:
        _validate_digits(self.digits, 44, "barcode")

    @property
    def bank_code(self) -> str:
        return self.digits[0:3]

    @property
    def currency(self) -> str:
        return self.digits[3]

    @property
    def general_dv(self) -> str:
        return self.digits[4]

    @property
    def due_factor(self) -> int:
        return int(self.digits[5:9])

    @property
    def amount_cents(self) -> int:
        return int(self.digits[9:19])

    @property
    def free_field(self) -> str:
        return self.digits[19:44]

    def general_dv_is_valid(self) -> bool:
        data = self.digits[0:4] + self.digits[5:44]
        return mod11(data) == int(self.general_dv)

    def dv_errors(self, directory: BankDirectory | None = None) -> tuple[DvError, ...]:
        if self.general_dv_is_valid():
            return ()
        data = self.digits[0:4] + self.digits[5:44]
        return (
            DvError(
                field="general",
                expected=mod11(data),
                actual=int(self.general_dv),
                algorithm=DvAlgorithm.MOD11,
                source=MANUAL_FEBRABAN,
            ),
        )

    def to_line(self, directory: BankDirectory | None = None) -> "BankDigitableLine":
        free = self.free_field
        field1 = self.digits[0:4] + free[0:5]
        field2 = free[5:15]
        field3 = free[15:25]
        algorithm = (
            directory.field_dv_algorithm(self.bank_code, 3)
            if directory is not None
            else DvAlgorithm.MOD10
        )
        field3_dv = mod11(field3) if algorithm is DvAlgorithm.MOD11 else mod10(field3)
        return BankDigitableLine(
            field1
            + str(mod10(field1))
            + field2
            + str(mod10(field2))
            + field3
            + str(field3_dv)
            + self.general_dv
            + self.digits[5:19],
        )


@dataclass(frozen=True, slots=True)
class BankDigitableLine:
    digits: str

    def __post_init__(self) -> None:
        _validate_digits(self.digits, 47, "bank digitable line")

    @property
    def bank_code(self) -> str:
        return self.digits[0:3]

    @property
    def currency(self) -> str:
        return self.digits[3]

    @property
    def free_field(self) -> str:
        return self.digits[4:9] + self.digits[10:20] + self.digits[21:31]

    @property
    def general_dv(self) -> str:
        return self.digits[32]

    @property
    def due_factor(self) -> int:
        return int(self.digits[33:37])

    @property
    def amount_cents(self) -> int:
        return int(self.digits[37:47])

    def field_data(self, field: int) -> str:
        if field == 1:
            return self.digits[0:9]
        if field == 2:
            return self.digits[10:20]
        if field == 3:
            return self.digits[21:31]
        raise ValueError("field must be 1, 2 or 3")

    def field_dv(self, field: int) -> int:
        if field == 1:
            return int(self.digits[9])
        if field == 2:
            return int(self.digits[20])
        if field == 3:
            return int(self.digits[31])
        raise ValueError("field must be 1, 2 or 3")

    def to_barcode(self) -> Barcode:
        return Barcode(
            self.digits[0:4] + self.general_dv + self.digits[33:47] + self.free_field,
        )

    def dv_errors(self, directory: BankDirectory | None = None) -> tuple[DvError, ...]:
        errors: list[DvError] = []
        for field in (1, 2, 3):
            data = self.field_data(field)
            actual = self.field_dv(field)
            algorithm = (
                directory.field_dv_algorithm(self.bank_code, field)
                if directory is not None
                else DvAlgorithm.MOD10
            )
            expected = mod11(data) if algorithm is DvAlgorithm.MOD11 else mod10(data)
            if expected == actual:
                continue
            source = (
                directory.field_dv_source(self.bank_code, field)
                if directory is not None
                else MANUAL_FEBRABAN
            )
            errors.append(
                DvError(
                    field=str(field),
                    expected=expected,
                    actual=actual,
                    algorithm=algorithm,
                    source=source,
                ),
            )

        errors.extend(self.to_barcode().dv_errors(directory))
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class UtilityDigitableLine:
    digits: str

    def __post_init__(self) -> None:
        _validate_digits(self.digits, 48, "utility digitable line")

    def to_barcode(self) -> Barcode:
        raise NotVerifiableLayoutError()
