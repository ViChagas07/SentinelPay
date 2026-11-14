from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

FEBRABAN_BASE_DATE = date(1997, 10, 7)

_ITF_WEIGHTS = (2, 1)


def mod10(data: str) -> int:
    total = 0
    weight_index = 0
    for char in reversed(data):
        product = int(char) * _ITF_WEIGHTS[weight_index]
        total += product // 10 + product % 10
        weight_index = 1 - weight_index
    return (10 - (total % 10)) % 10


def mod11(data: str) -> int:
    total = 0
    weight = 2
    for char in reversed(data):
        total += int(char) * weight
        weight = 2 if weight == 9 else weight + 1
    remainder = total % 11
    return 1 if remainder in (0, 1) else 11 - remainder


def format_brl(cents: int) -> str:
    integer, fraction = divmod(cents, 100)
    whole = f"{integer:,}".replace(",", ".")
    return f"R$ {whole},{fraction:02d}"


def format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def format_line(digits: str) -> str:
    if len(digits) != 47:
        raise ValueError("line must have 47 digits")
    groups = (
        digits[0:5],
        digits[5:10],
        digits[10:15],
        digits[15:21],
        digits[21:26],
        digits[26:32],
        digits[32:33],
        digits[33:47],
    )
    return (
        f"{groups[0]}.{groups[1]} {groups[2]}.{groups[3]} "
        f"{groups[4]}.{groups[5]} {groups[6]} {groups[7]}"
    )


@dataclass(frozen=True, slots=True)
class SyntheticBoleto:
    bank: str
    currency: str
    free_field: str
    factor: int
    amount_cents: int
    barcode: str
    line: str
    due_date: date | None
    header: str
    beneficiary: str
    beneficiary_tax_id: str
    payer: str
    payer_tax_id: str
    include_barcode_text: bool = False

    @property
    def formatted_line(self) -> str:
        return format_line(self.line)

    def ocr_text(self) -> str:
        lines = [
            self.header,
            f"BENEFICIARIO: {self.beneficiary}",
            f"CNPJ: {self.beneficiary_tax_id}",
            f"PAGADOR: {self.payer}",
            f"CPF: {self.payer_tax_id}",
            "AGENCIA: 1234 CONTA: 56789-0",
            "NOSSO NUMERO: 12345678901",
            f"VALOR DO DOCUMENTO: {format_brl(self.amount_cents)}",
        ]
        if self.due_date is not None:
            lines.append(f"VENCIMENTO: {format_date(self.due_date)}")
        lines.append(f"LINHA DIGITAVEL: {self.formatted_line}")
        if self.include_barcode_text:
            lines.append(f"CODIGO DE BARRAS: {self.barcode}")
        return "\n".join(lines)


_BANK_HEADERS = {
    "001": "BANCO DO BRASIL S.A.  001",
    "033": "BANCO SANTANDER S.A.  033",
    "104": "CAIXA ECONOMICA FEDERAL  104",
    "237": "BANCO BRADESCO S.A.  237",
    "341": "BANCO ITAU S.A.  341",
}


def build_boleto(
    *,
    bank: str = "341",
    currency: str = "9",
    free_field: str = "1234567890123456789012345",
    factor: int = 9000,
    amount_cents: int = 123456,
    beneficiary: str = "PAGAMENTOS SINTETICOS LTDA",
    beneficiary_tax_id: str = "11.222.333/0001-81",
    payer: str = "CLIENTE SINTETICO",
    payer_tax_id: str = "123.456.789-09",
    header: str | None = None,
    include_barcode_text: bool = False,
) -> SyntheticBoleto:
    if len(bank) != 3 or not bank.isdigit():
        raise ValueError("bank must have 3 digits")
    if len(currency) != 1 or not currency.isdigit():
        raise ValueError("currency must have 1 digit")
    if len(free_field) != 25 or not free_field.isdigit():
        raise ValueError("free_field must have 25 digits")
    if not 0 <= factor <= 9999:
        raise ValueError("factor out of range")
    if not 0 <= amount_cents <= 9_999_999_999:
        raise ValueError("amount out of range")

    tail = f"{factor:04d}{amount_cents:010d}{free_field}"
    general_dv = mod11(bank + currency + tail)
    barcode = bank + currency + str(general_dv) + tail

    field1 = bank + currency + free_field[:5]
    field2 = free_field[5:15]
    field3 = free_field[15:25]
    field3_dv = mod11(field3) if bank == "237" else mod10(field3)
    line = (
        field1
        + str(mod10(field1))
        + field2
        + str(mod10(field2))
        + field3
        + str(field3_dv)
        + str(general_dv)
        + f"{factor:04d}{amount_cents:010d}"
    )

    due_date = None if factor == 0 else FEBRABAN_BASE_DATE + timedelta(days=factor)
    return SyntheticBoleto(
        bank=bank,
        currency=currency,
        free_field=free_field,
        factor=factor,
        amount_cents=amount_cents,
        barcode=barcode,
        line=line,
        due_date=due_date,
        header=header or _BANK_HEADERS.get(bank, f"BANCO {bank}"),
        beneficiary=beneficiary,
        beneficiary_tax_id=beneficiary_tax_id,
        payer=payer,
        payer_tax_id=payer_tax_id,
        include_barcode_text=include_barcode_text,
    )


def decimal_value(cents: int) -> Decimal:
    return Decimal(cents) / Decimal(100)
