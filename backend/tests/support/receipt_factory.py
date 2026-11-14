from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from paysentineliq.domain.boleto.digits import mod10

_BLOCKS = ("83620000001", "00000000002", "00000000003", "00000000004")


def _line_from_blocks(blocks: tuple[str, ...], algorithm: str = "mod10") -> str:
    parts: list[str] = []
    for block in blocks:
        dv = mod10(block)
        if algorithm == "mod11":
            from paysentineliq.domain.boleto.digits import mod11

            dv = mod11(block)
        parts.append(f"{block}{dv}")
    return "".join(parts)


@dataclass(frozen=True, slots=True)
class SyntheticReceipt:
    issuer: str | None = "Energia Sul Distribuidora"
    amount: Decimal | None = Decimal("184.75")
    due_date: date | None = date(2026, 1, 15)
    reference: str | None = "01/2026"
    blocks: tuple[str, ...] = _BLOCKS
    include_barcode: bool = True
    extra_lines: tuple[str, ...] = ()
    dv_algorithm: str = "mod10"
    line_override: str | None = None
    barcode_override: str | None = None

    @property
    def line(self) -> str:
        if self.line_override is not None:
            return self.line_override
        return _line_from_blocks(self.blocks, self.dv_algorithm)

    @property
    def barcode(self) -> str:
        if self.barcode_override is not None:
            return self.barcode_override
        return "".join(self.blocks)

    def formatted_line(self) -> str:
        digits = self.line
        return " ".join(digits[index : index + 12] for index in range(0, 48, 12))

    def ocr_text(self) -> str:
        lines: list[str] = []
        if self.issuer is not None:
            lines.append(f"CONCESSIONARIA: {self.issuer}")
        if self.reference is not None:
            lines.append(f"REFERENCIA: {self.reference}")
        if self.amount is not None:
            lines.append(f"VALOR TOTAL: R$ {self.amount:.2f}".replace(".", ","))
        if self.due_date is not None:
            lines.append(f"VENCIMENTO: {self.due_date:%d/%m/%Y}")
        lines.append(f"LINHA DIGITAVEL: {self.formatted_line()}")
        if self.include_barcode:
            lines.append(f"CODIGO DE BARRAS: {self.barcode}")
        lines.extend(self.extra_lines)
        return "\n".join(lines)

    def with_extra(self, *lines: str) -> "SyntheticReceipt":
        return replace(self, extra_lines=self.extra_lines + lines)

    def with_tampered_dv(self) -> "SyntheticReceipt":
        digits = list(self.line)
        for position in (11, 23, 35, 47):
            digits[position] = str((int(digits[position]) + 5) % 10)
        tampered = "".join(digits)
        return replace(self, line_override=tampered)

    def with_tampered_barcode(self) -> "SyntheticReceipt":
        digits = list(self.barcode)
        digits[0] = "0" if digits[0] != "0" else "1"
        tampered = "".join(digits)
        return replace(self, barcode_override=tampered)


def build_receipt(**overrides: object) -> SyntheticReceipt:
    return SyntheticReceipt(**overrides)  # type: ignore[arg-type]
