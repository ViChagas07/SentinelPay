import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Generic, TypeVar, cast

from paysentineliq.domain.boleto.tax_id import Cnpj, Cpf, parse_tax_id
from paysentineliq.domain.payslip.models import ItemCategory, ItemKind, YearMonth

T = TypeVar("T", covariant=True)

_AMOUNT_RE = re.compile(
    r"(?<![\d.,])(?:R\$\s*)?(?P<sign>-)?"
    r"(?P<whole>[0-9OoIiLl|!]{1,3}(?:\.[0-9OoIiLl|!]{3})*|[0-9OoIiLl|!]+)"
    r",(?P<fraction>[0-9OoIiLl|!]{2,5})(?![\d])",
    re.IGNORECASE,
)
_CNPJ_FORMATTED_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
_CPF_FORMATTED_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_CNPJ_PLAIN_RE = re.compile(r"\b\d{14}\b")
_CPF_PLAIN_RE = re.compile(r"\b\d{11}\b")
_COMPETENCY_RE = re.compile(r"\b(0?[1-9]|1[0-2])\s*[/-]\s*(\d{4})\b")
_COMPETENCY_YEAR_FIRST_RE = re.compile(r"\b(\d{4})\s*[/-]\s*(0?[1-9]|1[0-2])\b")
_MONTH_NAME_RE = re.compile(
    r"\b(JANEIRO|FEVEREIRO|MARCO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)\s*[/-]\s*(\d{4})\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%")
_INTEGER_RE = re.compile(r"\b(\d{1,3})\b")
_LEADING_CODE_RE = re.compile(r"^\s*\d{2,6}\s*[-.]?\s*")

_OCR_DIGIT_MAP = {
    "O": "0",
    "o": "0",
    "I": "1",
    "i": "1",
    "l": "1",
    "L": "1",
    "|": "1",
    "!": "1",
}
_MONTHS = {
    "JANEIRO": 1,
    "FEVEREIRO": 2,
    "MARCO": 3,
    "ABRIL": 4,
    "MAIO": 5,
    "JUNHO": 6,
    "JULHO": 7,
    "AGOSTO": 8,
    "SETEMBRO": 9,
    "OUTUBRO": 10,
    "NOVEMBRO": 11,
    "DEZEMBRO": 12,
}

_EMPLOYER_LABELS = ("EMPRESA", "EMPREGADOR", "RAZAO SOCIAL", "RAZAO")
_EMPLOYEE_LABELS = ("FUNCIONARIO", "EMPREGADO", "NOME DO FUNCIONARIO", "NOME")
_TOTAL_EARNING_LABELS = (
    "TOTAL DE PROVENTOS",
    "TOTAL PROVENTOS",
    "TOTAL DE VENCIMENTOS",
    "TOTAL VENCIMENTOS",
    "TOTAL BRUTO",
)
_TOTAL_DEDUCTION_LABELS = ("TOTAL DE DESCONTOS", "TOTAL DESCONTOS")
_NET_LABELS = ("VALOR LIQUIDO", "LIQUIDO A RECEBER", "LIQUIDO")
_IRRF_BASE_LABELS = ("BASE CALCULO IRRF", "BASE DO IRRF", "BASE IRRF")
_DEPENDENT_LABELS = ("NUMERO DE DEPENDENTES", "N DEPENDENTES", "DEPENDENTES")
_METADATA_MARKERS = (
    "EMPRESA",
    "EMPREGADOR",
    "RAZAO SOCIAL",
    "FUNCIONARIO",
    "EMPREGADO",
    "CNPJ",
    "CPF",
    "COMPETENCIA",
    "MES/ANO",
    "PERIODO",
    "REFERENCIA",
    "DEPENDENTES",
)
_STOP_LABELS = (
    "CNPJ",
    "CPF",
    "COMPETENCIA",
    "MES/ANO",
    "PERIODO",
    "DEPENDENTES",
    "PROVENTOS",
    "DESCONTOS",
)


@dataclass(frozen=True, slots=True)
class ExtractedField(Generic[T]):
    value: T
    confidence: float
    raw: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ExtractedItem:
    description: str
    kind: ItemKind
    category: ItemCategory
    amount: Decimal
    overtime_percent: Decimal | None
    confidence: float
    raw: str


@dataclass(frozen=True, slots=True)
class PayslipFields:
    employer_name: ExtractedField[str] | None = None
    employer_cnpj: ExtractedField[Cnpj] | None = None
    employee_name: ExtractedField[str] | None = None
    employee_cpf: ExtractedField[Cpf] | None = None
    competency: ExtractedField[YearMonth] | None = None
    items: tuple[ExtractedItem, ...] = ()
    total_earnings: ExtractedField[Decimal] | None = None
    total_deductions: ExtractedField[Decimal] | None = None
    net: ExtractedField[Decimal] | None = None
    irrf_base: ExtractedField[Decimal] | None = None
    dependents: ExtractedField[int] | None = None
    layout_confidence: float = 0.0
    layout_recognized: bool = False


@dataclass(frozen=True, slots=True)
class _Line:
    index: int
    original: str
    folded: str


@dataclass(frozen=True, slots=True)
class _ParsedAmount:
    value: Decimal
    negative: bool
    start: int
    end: int
    raw: str
    corrections: int


def _fold(text: str) -> str:
    folded: list[str] = []
    for char in text:
        decomposed = unicodedata.normalize("NFKD", char)
        base = "".join(item for item in decomposed if not unicodedata.combining(item))
        folded.append(base.lower() if len(base) == 1 else char.lower())
    return "".join(folded)


def _normalize_ocr_number(text: str) -> tuple[str, int]:
    corrections = 0
    normalized: list[str] = []
    for char in text:
        replacement = _OCR_DIGIT_MAP.get(char)
        if replacement is None:
            normalized.append(char)
        else:
            normalized.append(replacement)
            corrections += 1
    return "".join(normalized), corrections


def _lines(text: str) -> tuple[_Line, ...]:
    return tuple(
        _Line(index=index, original=line.strip(), folded=_fold(line.strip()))
        for index, line in enumerate(text.splitlines())
        if line.strip()
    )


def _parse_amount(line: _Line) -> _ParsedAmount | None:
    matches = list(_AMOUNT_RE.finditer(line.folded))
    if not matches:
        return None
    match = matches[-1]
    raw_number = match.group("whole") + "," + match.group("fraction")
    normalized, corrections = _normalize_ocr_number(raw_number)
    try:
        value = Decimal(normalized.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None
    return _ParsedAmount(
        value=value,
        negative=match.group("sign") == "-",
        start=match.start(),
        end=match.end(),
        raw=raw_number,
        corrections=corrections,
    )


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    folded = text.lower()
    return any(needle.lower() in folded for needle in needles)


def _is_total_line(folded: str) -> bool:
    return _contains_any(
        folded,
        (
            *_TOTAL_EARNING_LABELS,
            *_TOTAL_DEDUCTION_LABELS,
            *_NET_LABELS,
            *_IRRF_BASE_LABELS,
        ),
    )


def _is_metadata_line(folded: str) -> bool:
    return _contains_any(folded, _METADATA_MARKERS)


def _section_kind(folded: str, amount: _ParsedAmount | None) -> ItemKind | None:
    if amount is not None:
        return None
    if "desconto" in folded:
        return ItemKind.DEDUCTION
    if "provento" in folded or "vencimento" in folded:
        return ItemKind.EARNING
    return None


def _clean_description(original: str, folded: str, start: int) -> str:
    raw = original[:start] if len(original) == len(folded) else folded[:start]
    raw = _LEADING_CODE_RE.sub("", raw)
    return " ".join(raw.strip(" :-.;").split())


def _parse_percent(folded_description: str) -> Decimal | None:
    match = _PERCENT_RE.search(folded_description)
    if match is None:
        return None
    raw = match.group(1).replace(",", ".")
    try:
        return Decimal(raw) / Decimal(100)
    except InvalidOperation:
        return None


def _classify_item(
    folded_description: str,
    section: ItemKind | None,
    negative: bool,
) -> tuple[ItemKind, ItemCategory, bool]:
    if "fgts" in folded_description:
        return ItemKind.INFO, ItemCategory.FGTS, True
    if "base calculo" in folded_description or "base de calculo" in folded_description:
        return ItemKind.INFO, ItemCategory.OTHER, True
    if "inss" in folded_description:
        return ItemKind.DEDUCTION, ItemCategory.INSS, True
    if "irrf" in folded_description or "imposto de renda" in folded_description:
        return ItemKind.DEDUCTION, ItemCategory.IRRF, True
    if "salario familia" in folded_description:
        return ItemKind.EARNING, ItemCategory.OTHER, True
    if _contains_any(
        folded_description,
        ("salario base", "salario contratual", "salario normal", "salario"),
    ):
        return ItemKind.EARNING, ItemCategory.BASE_SALARY, True
    if _contains_any(
        folded_description,
        ("horas extras", "hora extra", "h.e.", "he ", "extra"),
    ):
        return ItemKind.EARNING, ItemCategory.OVERTIME, True
    if _contains_any(
        folded_description,
        (
            "desconto",
            "vale",
            "adiantamento",
            "emprestimo",
            "pensao",
            "contribuicao",
            "sindical",
            "transporte",
            "refeicao",
            "alimentacao",
            "saude",
            "odonto",
            "seguro",
            "falta",
            "atraso",
            "previdencia",
        ),
    ):
        return ItemKind.DEDUCTION, ItemCategory.OTHER, True
    if _contains_any(
        folded_description,
        (
            "provento",
            "bonus",
            "gratificacao",
            "comissao",
            "adicional",
            "ferias",
            "13o",
            "decimo terceiro",
            "dsr",
        ),
    ):
        return ItemKind.EARNING, ItemCategory.OTHER, True
    if negative:
        return ItemKind.DEDUCTION, ItemCategory.OTHER, False
    if section is not None:
        return section, ItemCategory.OTHER, False
    return ItemKind.UNKNOWN, ItemCategory.OTHER, False


def _item_confidence(classified_by_keyword: bool, corrections: int) -> float:
    base = 0.95 if classified_by_keyword else 0.8
    if corrections:
        base -= 0.03 * corrections
    return max(0.3, min(1.0, base))


def _extract_items(lines: tuple[_Line, ...]) -> tuple[ExtractedItem, ...]:
    items: list[ExtractedItem] = []
    section: ItemKind | None = None
    for line in lines:
        amount = _parse_amount(line)
        new_section = _section_kind(line.folded, amount)
        if new_section is not None:
            section = new_section
            continue
        if amount is None:
            continue
        if _is_total_line(line.folded) or _is_metadata_line(line.folded):
            continue
        description = _clean_description(line.original, line.folded, amount.start)
        if len(description) < 2:
            continue
        folded_description = _fold(description)
        kind, category, classified_by_keyword = _classify_item(
            folded_description,
            section,
            amount.negative,
        )
        if amount.negative:
            kind = ItemKind.DEDUCTION
        items.append(
            ExtractedItem(
                description=description,
                kind=kind,
                category=category,
                amount=abs(amount.value),
                overtime_percent=_parse_percent(folded_description),
                confidence=_item_confidence(classified_by_keyword, amount.corrections),
                raw=line.original,
            ),
        )
    return tuple(items)


def _label_remainder(folded: str, labels: tuple[str, ...]) -> tuple[str, str] | None:
    for label in labels:
        index = folded.find(label.lower())
        if index < 0:
            continue
        remainder = folded[index + len(label) :].lstrip(" :-")
        for stop in _STOP_LABELS:
            stop_index = remainder.find(stop.lower())
            if stop_index >= 0:
                remainder = remainder[:stop_index]
        remainder = remainder.strip(" :-.;")
        if remainder:
            return label, remainder
    return None


def _extract_name(
    lines: tuple[_Line, ...],
    labels: tuple[str, ...],
) -> ExtractedField[str] | None:
    for line in lines:
        match = _label_remainder(line.folded, labels)
        if match is None:
            continue
        _, folded_value = match
        value = (
            line.original[line.folded.find(folded_value) :][: len(folded_value)].strip()
            if len(line.original) == len(line.folded)
            else folded_value
        )
        if any(char.isalpha() for char in value):
            return ExtractedField(value=value, confidence=0.95, raw=line.original)
    return None


def _extract_formatted_tax_id(
    lines: tuple[_Line, ...],
    formatted_re: re.Pattern[str],
    plain_re: re.Pattern[str],
    label: str,
) -> ExtractedField[Cpf | Cnpj] | None:
    plain_candidate: tuple[str, str] | None = None
    for line in lines:
        match = formatted_re.search(line.folded)
        if match is not None:
            tax_id = parse_tax_id(match.group(0))
            if tax_id is not None:
                confidence = 1.0 if label in line.folded else 0.8
                return ExtractedField(value=tax_id, confidence=confidence, raw=line.original)
        if label in line.folded and plain_candidate is None:
            plain_match = plain_re.search(line.folded)
            if plain_match is not None:
                plain_candidate = (plain_match.group(0), line.original)
    if plain_candidate is not None:
        tax_id = parse_tax_id(plain_candidate[0])
        if tax_id is not None:
            return ExtractedField(value=tax_id, confidence=0.95, raw=plain_candidate[1])
    return None


def _extract_competency(
    lines: tuple[_Line, ...],
) -> ExtractedField[YearMonth] | None:
    candidates: list[tuple[YearMonth, float, str]] = []
    for line in lines:
        labelled = _contains_any(
            line.folded,
            ("competencia", "mes/ano", "periodo", "referencia"),
        )
        confidence = 0.95 if labelled else 0.6
        match = _COMPETENCY_RE.search(line.folded)
        if match is not None:
            candidates.append(
                (
                    YearMonth(int(match.group(2)), int(match.group(1))),
                    confidence,
                    line.original,
                ),
            )
            continue
        match = _COMPETENCY_YEAR_FIRST_RE.search(line.folded)
        if match is not None:
            candidates.append(
                (
                    YearMonth(int(match.group(1)), int(match.group(2))),
                    confidence,
                    line.original,
                ),
            )
            continue
        match = _MONTH_NAME_RE.search(line.folded)
        if match is not None:
            candidates.append(
                (
                    YearMonth(int(match.group(2)), _MONTHS[match.group(1).upper()]),
                    confidence,
                    line.original,
                ),
            )
    if not candidates:
        return None
    candidates.sort(key=lambda item: -item[1])
    value, confidence, raw = candidates[0]
    return ExtractedField(value=value, confidence=confidence, raw=raw)


def _extract_total(
    lines: tuple[_Line, ...],
    labels: tuple[str, ...],
) -> ExtractedField[Decimal] | None:
    for line in lines:
        if not _contains_any(line.folded, labels):
            continue
        amount = _parse_amount(line)
        if amount is None:
            continue
        value = -amount.value if amount.negative else amount.value
        return ExtractedField(value=value, confidence=1.0, raw=line.original)
    return None


def _extract_dependents(lines: tuple[_Line, ...]) -> ExtractedField[int] | None:
    for line in lines:
        if not _contains_any(line.folded, _DEPENDENT_LABELS):
            continue
        match = _INTEGER_RE.search(line.folded)
        if match is not None:
            return ExtractedField(value=int(match.group(1)), confidence=0.9, raw=line.original)
    return None


def extract_payslip_fields(text: str) -> PayslipFields:
    lines = _lines(text)
    employer_name = _extract_name(lines, _EMPLOYER_LABELS)
    employee_name = _extract_name(lines, _EMPLOYEE_LABELS)
    employer_cnpj = cast(
        ExtractedField[Cnpj] | None,
        _extract_formatted_tax_id(
            lines,
            _CNPJ_FORMATTED_RE,
            _CNPJ_PLAIN_RE,
            "cnpj",
        ),
    )
    employee_cpf = cast(
        ExtractedField[Cpf] | None,
        _extract_formatted_tax_id(
            lines,
            _CPF_FORMATTED_RE,
            _CPF_PLAIN_RE,
            "cpf",
        ),
    )
    competency = _extract_competency(lines)
    total_earnings = _extract_total(lines, _TOTAL_EARNING_LABELS)
    total_deductions = _extract_total(lines, _TOTAL_DEDUCTION_LABELS)
    net = _extract_total(lines, _NET_LABELS)
    irrf_base = _extract_total(lines, _IRRF_BASE_LABELS)
    items = _extract_items(lines)

    anchors = (
        employer_name is not None,
        employer_cnpj is not None,
        employee_name is not None,
        employee_cpf is not None,
        competency is not None,
        total_earnings is not None,
        total_deductions is not None,
        net is not None,
        len(items) >= 2,
    )
    recognized_count = sum(anchors)
    return PayslipFields(
        employer_name=employer_name,
        employer_cnpj=employer_cnpj,
        employee_name=employee_name,
        employee_cpf=employee_cpf,
        competency=competency,
        items=items,
        total_earnings=total_earnings,
        total_deductions=total_deductions,
        net=net,
        irrf_base=irrf_base,
        dependents=_extract_dependents(lines),
        layout_confidence=recognized_count / len(anchors),
        layout_recognized=recognized_count >= 5,
    )
