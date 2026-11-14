from dataclasses import dataclass

_ASCII_DIGITS = frozenset("0123456789")
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


@dataclass(frozen=True, slots=True)
class NormalizedDigits:
    text: str
    corrections: int


def normalize_ocr_digits(text: str) -> NormalizedDigits:
    corrections = 0
    normalized: list[str] = []
    for char in text:
        replacement = _OCR_DIGIT_MAP.get(char)
        if replacement is None:
            normalized.append(char)
        else:
            normalized.append(replacement)
            corrections += 1
    return NormalizedDigits(text="".join(normalized), corrections=corrections)


def only_digits(text: str) -> str:
    return "".join(char for char in text if char in _ASCII_DIGITS)


def _ensure_digits(data: str) -> None:
    if not data or any(char not in _ASCII_DIGITS for char in data):
        raise ValueError("data must contain only ASCII digits")


def mod10(data: str) -> int:
    _ensure_digits(data)
    total = 0
    weight = 2
    for char in reversed(data):
        product = int(char) * weight
        total += product // 10 + product % 10
        weight = 1 if weight == 2 else 2
    return (10 - (total % 10)) % 10


def mod11(data: str) -> int:
    _ensure_digits(data)
    total = 0
    weight = 2
    for char in reversed(data):
        total += int(char) * weight
        weight = 2 if weight == 9 else weight + 1
    remainder = total % 11
    return 1 if remainder in (0, 1) else 11 - remainder
