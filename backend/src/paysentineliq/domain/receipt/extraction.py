import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from paysentineliq.domain.boleto.bank_directory import BankDirectory
from paysentineliq.domain.boleto.digits import normalize_ocr_digits, only_digits
from paysentineliq.domain.boleto.extraction import ExtractedField, extract_boleto_fields

_DIGIT_GROUP_RE = re.compile(r"[0-9OoIiLl|!]+")
_AMOUNT_RE = re.compile(r"(?:R\$\s*)?((?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})")
_DATE_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b")
_ISSUER_RE = re.compile(
    r"\b(?:concessionaria|distribuidora|prestadora(?: de servicos)?|"
    r"companhia(?: de [a-z]+)?|saneamento|cia(?: de [a-z]+)?|emissor)\b"
    r"\s*:?\s*(.+)",
)
_REFERENCE_RE = re.compile(
    r"\b(?:referencia|ref|competencia|mes de referencia|periodo)\b"
    r"\s*:?\s*(.+)",
)
_STOP_RE = re.compile(
    r"\b(CNPJ|CPF|VALOR|VENCIMENTO|REFERENCIA|LINHA|CODIGO|DATA|TOTAL|PAGUE)\b",
)


@dataclass(frozen=True, slots=True)
class ReceiptFields:
    line: ExtractedField[str] | None = None
    barcode: ExtractedField[str] | None = None
    amount: ExtractedField[Decimal] | None = None
    due_date: ExtractedField[date] | None = None
    issuer: ExtractedField[str] | None = None
    reference: ExtractedField[str] | None = None
    amount_candidates: tuple[ExtractedField[Decimal], ...] = ()
    due_date_candidates: tuple[ExtractedField[date], ...] = ()


@dataclass(frozen=True, slots=True)
class _Line:
    original: str
    folded: str


def _fold(text: str) -> str:
    import unicodedata

    folded: list[str] = []
    for char in text:
        decomposed = unicodedata.normalize("NFKD", char)
        base = "".join(item for item in decomposed if not unicodedata.combining(item))
        folded.append(base.lower() if len(base) == 1 else char.lower())
    return "".join(folded)


def _lines(text: str) -> tuple[_Line, ...]:
    return tuple(
        _Line(original=line.strip(), folded=_fold(line.strip()))
        for line in text.splitlines()
        if line.strip()
    )


def _digit_text(line: str) -> tuple[str, int]:
    digits: list[str] = []
    corrections = 0
    for match in _DIGIT_GROUP_RE.finditer(line):
        normalized = normalize_ocr_digits(match.group(0))
        digits.append(only_digits(normalized.text))
        corrections += normalized.corrections
    return "".join(digits), corrections


def _extract_line(lines: tuple[_Line, ...]) -> ExtractedField[str] | None:
    candidates: list[tuple[str, int, float]] = []
    for line in lines:
        labelled = "linha digitavel" in line.folded or "linha digitável" in line.folded
        digits, corrections = _digit_text(line.folded)
        if len(digits) != 48:
            continue
        confidence = 0.98 if labelled else 0.75
        if corrections:
            confidence -= 0.03 * corrections
        candidates.append((digits, corrections, max(0.0, min(1.0, confidence))))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[2], reverse=True)
    digits, _, confidence = candidates[0]
    return ExtractedField(value=digits, confidence=confidence)


def _extract_barcode(lines: tuple[_Line, ...]) -> ExtractedField[str] | None:
    candidates: list[tuple[str, float]] = []
    for line in lines:
        labelled = "codigo de barras" in line.folded or "código de barras" in line.folded
        if not labelled:
            continue
        digits, corrections = _digit_text(line.folded)
        if len(digits) != 44:
            continue
        confidence = 0.98 - 0.03 * corrections
        candidates.append((digits, max(0.0, min(1.0, confidence))))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[1], reverse=True)
    digits, confidence = candidates[0]
    return ExtractedField(value=digits, confidence=confidence)


def _label_value(
    line: _Line,
    match: re.Match[str],
    *,
    require_alpha: bool = True,
) -> str | None:
    rest = match.group(1).strip(" :-")
    if not rest:
        return None
    stop = _STOP_RE.search(rest)
    if stop is not None:
        rest = rest[: stop.start()].strip(" :-")
    if len(rest) < 2 or (require_alpha and not any(char.isalpha() for char in rest)):
        return None
    if len(line.original) == len(line.folded):
        position = line.folded.find(rest, match.start(1))
        if position >= 0:
            return line.original[position : position + len(rest)].strip()
    return rest


def _extract_issuer(lines: tuple[_Line, ...]) -> ExtractedField[str] | None:
    for line in lines:
        match = _ISSUER_RE.search(line.folded)
        if match is None:
            continue
        value = _label_value(line, match)
        if value is None:
            continue
        return ExtractedField(value=value, confidence=0.95, raw=line.original)
    return None


def _extract_reference(lines: tuple[_Line, ...]) -> ExtractedField[str] | None:
    for line in lines:
        match = _REFERENCE_RE.search(line.folded)
        if match is None:
            continue
        value = _label_value(line, match, require_alpha=False)
        if value is None:
            continue
        return ExtractedField(value=value[:60], confidence=0.9, raw=line.original)
    return None


def _amount_candidates(lines: tuple[_Line, ...]) -> tuple[ExtractedField[Decimal], ...]:
    candidates: list[ExtractedField[Decimal]] = []
    for line in lines:
        if "linha digitavel" in line.folded or "codigo de barras" in line.folded:
            continue
        if len(_digit_text(line.folded)[0]) >= 44:
            continue
        if not any(
            label in line.folded for label in ("valor", "total", "pagar", "pague", "a pagar")
        ):
            continue
        for match in _AMOUNT_RE.finditer(line.folded):
            raw = match.group(1)
            value = Decimal(raw.replace(".", "").replace(",", "."))
            confidence = 1.0 if "valor total" in line.folded else 0.9
            candidates.append(
                ExtractedField(value=value, confidence=confidence, raw=match.group(0)),
            )
    return tuple(candidates)


def _due_date_candidates(lines: tuple[_Line, ...]) -> tuple[ExtractedField[date], ...]:
    candidates: list[ExtractedField[date]] = []
    for line in lines:
        if "emissao" in line.folded or "cnpj" in line.folded or "cpf" in line.folded:
            continue
        if "linha digitavel" in line.folded or "codigo de barras" in line.folded:
            continue
        if not any(
            label in line.folded for label in ("vencimento", "vence", "pague", "pagar", "ate")
        ):
            continue
        for match in _DATE_RE.finditer(line.folded):
            parsed = _parse_date(match.group(1), match.group(2), match.group(3))
            if parsed is None:
                continue
            confidence = 1.0 if "vencimento" in line.folded else 0.9
            candidates.append(
                ExtractedField(value=parsed, confidence=confidence, raw=match.group(0)),
            )
    return tuple(candidates)


def _parse_date(day: str, month: str, year: str) -> date | None:
    parsed_year = int(year)
    if len(year) == 2:
        parsed_year += 2000
    try:
        return date(parsed_year, int(month), int(day))
    except ValueError:
        return None


def extract_receipt_fields(
    text: str,
    *,
    bank_directory: BankDirectory | None = None,
) -> ReceiptFields:
    lines = _lines(text)
    base = extract_boleto_fields(text, bank_directory=bank_directory)
    line = _extract_line(lines)
    if line is None and base.line is not None and len(base.line.value) == 48:
        line = base.line
    barcode = _extract_barcode(lines)
    if barcode is None:
        barcode = base.barcode
    amounts = _amount_candidates(lines)
    due_dates = _due_date_candidates(lines)
    amount = base.amount or (max(amounts, key=lambda item: item.confidence) if amounts else None)
    due_date = base.due_date or (
        max(due_dates, key=lambda item: item.confidence) if due_dates else None
    )
    return ReceiptFields(
        line=line,
        barcode=barcode,
        amount=amount,
        due_date=due_date,
        issuer=_extract_issuer(lines),
        reference=_extract_reference(lines),
        amount_candidates=amounts,
        due_date_candidates=due_dates,
    )
