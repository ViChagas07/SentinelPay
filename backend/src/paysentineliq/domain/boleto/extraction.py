import itertools
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Generic, TypeVar

from paysentineliq.domain.boleto.bank_directory import EMPTY_BANK_DIRECTORY, BankDirectory
from paysentineliq.domain.boleto.digits import normalize_ocr_digits, only_digits
from paysentineliq.domain.boleto.tax_id import TaxId, parse_tax_id

T = TypeVar("T")

_RUN_RE = re.compile(r"[0-9OoIiLl|!.\-\s]+")
_AMOUNT_RE = re.compile(r"(?:R\$\s*)?((?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})")
_DATE_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b")
_ROLE_RE = re.compile(r"\b(BENEFICIARIO|CEDENTE|PAGADOR|SACADO)\b\s*:?\s*(.*)", re.IGNORECASE)
_STOP_RE = re.compile(
    r"\b(CNPJ|CPF|AGENCIA|CONTA|NOSSO NUMERO|VALOR|VENCIMENTO|LINHA DIGITAVEL|CODIGO DE BARRAS)\b",
)
_CNPJ_FORMATTED_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
_CPF_FORMATTED_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_UNFORMATTED_TAX_ID_RE = re.compile(r"\b\d{11,14}\b")
_BANK_CODE_RE = re.compile(r"\bBANCO\b[^\n]{0,30}?\b(\d{3})\b", re.IGNORECASE)
_ANY_BANK_CODE_RE = re.compile(r"\b(\d{3})\b", re.IGNORECASE)
_ABSENCE_PHRASES = ("sem vencimento", "nao vence", "sem data de vencimento")
_ROLE_LABELS = {
    "BENEFICIARIO": "beneficiary",
    "CEDENTE": "beneficiary",
    "PAGADOR": "payer",
    "SACADO": "payer",
}
_LABELS = frozenset(label.lower() for label in _ROLE_LABELS) | {"cnpj", "cpf"}


@dataclass(frozen=True, slots=True)
class ExtractedField(Generic[T]):
    value: T
    confidence: float
    raw: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class BankHeader:
    code: str
    name: str
    confidence: float
    raw: str


@dataclass(frozen=True, slots=True)
class BoletoFields:
    line: ExtractedField[str] | None = None
    barcode: ExtractedField[str] | None = None
    amount: ExtractedField[Decimal] | None = None
    due_date: ExtractedField[date] | None = None
    due_date_absent: bool = False
    beneficiary: ExtractedField[str] | None = None
    beneficiary_tax_id: ExtractedField[TaxId] | None = None
    payer: ExtractedField[str] | None = None
    payer_tax_id: ExtractedField[TaxId] | None = None
    additional_tax_ids: tuple[ExtractedField[TaxId], ...] = ()
    bank_header: ExtractedField[BankHeader] | None = None


@dataclass(frozen=True, slots=True)
class _Line:
    index: int
    original: str
    folded: str


def _fold(text: str) -> str:
    folded: list[str] = []
    for char in text:
        decomposed = unicodedata.normalize("NFKD", char)
        base = "".join(item for item in decomposed if not unicodedata.combining(item))
        folded.append(base.lower() if len(base) == 1 else char.lower())
    return "".join(folded)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _lines(text: str) -> tuple[_Line, ...]:
    return tuple(
        _Line(index=index, original=line.strip(), folded=_fold(line.strip()))
        for index, line in enumerate(text.splitlines())
        if line.strip()
    )


def _digit_runs(line: str) -> tuple[tuple[str, str, int], ...]:
    runs: list[tuple[str, str, int]] = []
    for match in _RUN_RE.finditer(line):
        raw = match.group(0).strip()
        if not raw:
            continue
        normalized = normalize_ocr_digits(raw)
        digits = only_digits(normalized.text)
        if len(digits) >= 4:
            runs.append((raw, digits, normalized.corrections))
    return tuple(runs)


def _line_confidence(line: str, corrections: int, *, split: bool) -> float:
    confidence = 0.8 if split else 1.0
    if corrections:
        confidence = min(confidence, 0.85) - 0.03 * corrections
    if "linha digitavel" in line:
        confidence += 0.05
    elif not split:
        confidence -= 0.05
    if split:
        confidence -= 0.05
    return _clamp(confidence)


def _extract_line(lines: tuple[_Line, ...]) -> ExtractedField[str] | None:
    candidates: list[tuple[str, str, int, float]] = []
    for line in lines:
        for raw, digits, corrections in _digit_runs(line.folded):
            if len(digits) not in (47, 48):
                continue
            candidates.append(
                (digits, raw, len(digits), _line_confidence(line.folded, corrections, split=False)),
            )

    for first, second in itertools.pairwise(lines):
        first_runs = _digit_runs(first.folded)
        second_runs = _digit_runs(second.folded)
        if not first_runs or not second_runs:
            continue
        raw_first, digits_first, corrections_first = max(first_runs, key=lambda run: len(run[1]))
        raw_second, digits_second, corrections_second = max(
            second_runs, key=lambda run: len(run[1])
        )
        if len(digits_first) < 10 or len(digits_second) < 10:
            continue
        combined = digits_first + digits_second
        if len(combined) not in (47, 48):
            continue
        label_line = f"{first.folded} {second.folded}"
        candidates.append(
            (
                combined,
                f"{raw_first} {raw_second}",
                len(combined),
                _line_confidence(
                    label_line,
                    corrections_first + corrections_second,
                    split=True,
                ),
            ),
        )

    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[3], item[0]))
    digits, raw, _, confidence = candidates[0]
    return ExtractedField(value=digits, confidence=confidence, raw=raw)


def _extract_barcode(lines: tuple[_Line, ...]) -> ExtractedField[str] | None:
    candidates: list[tuple[str, str, float]] = []
    for line in lines:
        for raw, digits, corrections in _digit_runs(line.folded):
            if len(digits) != 44:
                continue
            confidence = 0.6
            if "codigo de barras" in line.folded:
                confidence = 0.95
            if corrections:
                confidence -= 0.03 * corrections
            candidates.append((digits, raw, _clamp(confidence)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[2], item[0]))
    digits, raw, confidence = candidates[0]
    return ExtractedField(value=digits, confidence=confidence, raw=raw)


def _extract_amount(lines: tuple[_Line, ...]) -> ExtractedField[Decimal] | None:
    candidates: list[tuple[Decimal, str, float]] = []
    for line in lines:
        if "linha digitavel" in line.folded or "codigo de barras" in line.folded:
            continue
        for match in _AMOUNT_RE.finditer(line.folded):
            raw_number = match.group(1)
            value = Decimal(raw_number.replace(".", "").replace(",", "."))
            if "valor do documento" in line.folded:
                confidence = 1.0
            elif "valor" in line.folded and "r$" in line.folded:
                confidence = 0.98
            elif "r$" in line.folded:
                confidence = 0.9
            elif "valor" in line.folded:
                confidence = 0.85
            else:
                confidence = 0.65
            candidates.append((value, match.group(0), confidence))
    if not candidates:
        return None
    candidates.sort(key=lambda item: -item[2])
    value, raw, confidence = candidates[0]
    return ExtractedField(value=value, confidence=confidence, raw=raw)


def _parse_date(day: str, month: str, year: str) -> date | None:
    parsed_year = int(year)
    if len(year) == 2:
        parsed_year += 2000
    try:
        return date(parsed_year, int(month), int(day))
    except ValueError:
        return None


def _extract_due_date(lines: tuple[_Line, ...]) -> ExtractedField[date] | None:
    candidates: list[tuple[date, str, float]] = []
    for line in lines:
        if "cnpj" in line.folded or "cpf" in line.folded:
            continue
        if "linha digitavel" in line.folded or "codigo de barras" in line.folded:
            continue
        for match in _DATE_RE.finditer(line.folded):
            parsed = _parse_date(match.group(1), match.group(2), match.group(3))
            if parsed is None:
                continue
            if "emissao" in line.folded:
                continue
            confidence = 1.0 if "vencimento" in line.folded else 0.45
            candidates.append((parsed, match.group(0), confidence))
    if not candidates:
        return None
    candidates.sort(key=lambda item: -item[2])
    value, raw, confidence = candidates[0]
    return ExtractedField(value=value, confidence=confidence, raw=raw)


def _has_tax_label(line: str) -> bool:
    return "cnpj" in line or "cpf" in line


def _tax_ids_in_line(line: _Line) -> tuple[tuple[TaxId, float], ...]:
    if "linha digitavel" in line.folded or "codigo de barras" in line.folded:
        return ()
    if any(len(run[1]) >= 44 for run in _digit_runs(line.folded)):
        return ()

    labelled = _has_tax_label(line.folded) or _ROLE_RE.search(line.folded) is not None
    found: list[tuple[TaxId, float]] = []
    for pattern in (_CNPJ_FORMATTED_RE, _CPF_FORMATTED_RE):
        for match in pattern.finditer(line.folded):
            tax_id = parse_tax_id(match.group(0))
            if tax_id is None:
                continue
            found.append((tax_id, 1.0 if labelled else 0.8))
    if labelled:
        for match in _UNFORMATTED_TAX_ID_RE.finditer(line.folded):
            tax_id = parse_tax_id(match.group(0))
            if tax_id is None:
                continue
            found.append((tax_id, 0.9))
    return tuple(found)


def _role_name(
    line: _Line,
    match: re.Match[str],
    lines: tuple[_Line, ...],
) -> ExtractedField[str] | None:
    rest = match.group(2).strip(" :-")
    value = rest
    if rest:
        stop = _STOP_RE.search(rest)
        if stop is not None:
            rest = rest[: stop.start()].strip(" :-")
            value = rest
        raw_rest = match.group(2)
        leading = len(raw_rest) - len(raw_rest.lstrip(" :-"))
        start = match.start(2) + leading
        if len(line.original) == len(line.folded):
            position = line.folded.find(rest, start)
            if position >= 0:
                value = line.original[position : position + len(rest)].strip()
    confidence = 0.95
    if not rest:
        if line.index + 1 >= len(lines):
            return None
        following = lines[line.index + 1]
        if _ROLE_RE.search(following.folded) or _has_tax_label(following.folded):
            return None
        if not any(char.isalpha() for char in following.folded):
            return None
        rest = following.folded
        value = (
            following.original
            if len(following.original) == len(following.folded)
            else following.folded
        )
        confidence = 0.8
    if len(rest) < 3 or _has_tax_label(rest) or rest in _LABELS:
        return None
    return ExtractedField(value=value, confidence=confidence, raw=line.original)


def _extract_parties(
    lines: tuple[_Line, ...],
) -> tuple[
    ExtractedField[str] | None,
    ExtractedField[str] | None,
    ExtractedField[TaxId] | None,
    ExtractedField[TaxId] | None,
    tuple[ExtractedField[TaxId], ...],
]:
    beneficiary: ExtractedField[str] | None = None
    payer: ExtractedField[str] | None = None
    beneficiary_tax_id: ExtractedField[TaxId] | None = None
    payer_tax_id: ExtractedField[TaxId] | None = None
    additional: list[ExtractedField[TaxId]] = []
    current_role: str | None = None

    for line in lines:
        role_match = _ROLE_RE.search(line.folded)
        role: str | None = None
        if role_match is not None:
            role = _ROLE_LABELS[role_match.group(1).upper()]
            current_role = role
            name = _role_name(line, role_match, lines)
            if name is not None:
                if role == "beneficiary" and beneficiary is None:
                    beneficiary = name
                elif role == "payer" and payer is None:
                    payer = name

        for tax_id, confidence in _tax_ids_in_line(line):
            target_role = role or current_role
            field = ExtractedField(value=tax_id, confidence=confidence, raw=line.original)
            if target_role == "beneficiary":
                if beneficiary_tax_id is None or confidence > beneficiary_tax_id.confidence:
                    beneficiary_tax_id = field
            elif target_role == "payer":
                if payer_tax_id is None or confidence > payer_tax_id.confidence:
                    payer_tax_id = field
            elif all(existing.value.digits != tax_id.digits for existing in additional):
                additional.append(field)

    return beneficiary, payer, beneficiary_tax_id, payer_tax_id, tuple(additional)


def _extract_bank_header(
    lines: tuple[_Line, ...],
    directory: BankDirectory,
) -> ExtractedField[BankHeader] | None:
    for line in lines[:6]:
        if any(len(run[1]) >= 44 for run in _digit_runs(line.folded)):
            continue
        bank = directory.find_by_name(line.folded)
        code_match = _BANK_CODE_RE.search(line.folded)
        if code_match is None:
            code_match = _ANY_BANK_CODE_RE.search(line.folded)
        if bank is None and (code_match is None or "banco" not in line.folded):
            continue
        if bank is None and code_match is None:
            continue
        if code_match is not None and bank is not None:
            code = code_match.group(1)
            confidence = 0.95 if code == bank.code else 0.8
        elif code_match is not None:
            code = code_match.group(1)
            confidence = 0.8
        elif bank is not None:
            code = bank.code
            confidence = 0.9
        else:
            continue
        name = bank.name if bank is not None else f"BANCO {code}"
        header = BankHeader(code=code, name=name, confidence=confidence, raw=line.original)
        return ExtractedField(value=header, confidence=confidence, raw=line.original)
    return None


def extract_boleto_fields(
    text: str,
    *,
    bank_directory: BankDirectory | None = None,
) -> BoletoFields:
    directory = bank_directory or EMPTY_BANK_DIRECTORY
    lines = _lines(text)
    folded_text = "\n".join(line.folded for line in lines)
    due_date = _extract_due_date(lines)
    due_date_absent = due_date is None and any(phrase in folded_text for phrase in _ABSENCE_PHRASES)
    beneficiary, payer, beneficiary_tax_id, payer_tax_id, additional = _extract_parties(lines)
    return BoletoFields(
        line=_extract_line(lines),
        barcode=_extract_barcode(lines),
        amount=_extract_amount(lines),
        due_date=due_date,
        due_date_absent=due_date_absent,
        beneficiary=beneficiary,
        beneficiary_tax_id=beneficiary_tax_id,
        payer=payer,
        payer_tax_id=payer_tax_id,
        additional_tax_ids=additional,
        bank_header=_extract_bank_header(lines, directory),
    )
