import re

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")),
    ("bearer_token", re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}")),
    (
        "secret_assignment",
        re.compile(r"(?i)\b(token|api[_-]?key|secret|password)\b\s*[=:]\s*[\"']?[^\s\"',;]{4,}"),
    ),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("cnpj", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
    ("cpf", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"(?<!\w)(?:\+?55[\s.-]?)?\(?\d{2}\)?[\s.-]?\d{4,5}[\s.-]?\d{4}(?!\w)")),
)

_MASK_LABELS = {
    "jwt": "[REDACTED_JWT]",
    "bearer_token": "Bearer [REDACTED_TOKEN]",
    "aws_access_key": "[REDACTED_AWS_KEY]",
    "private_key": "[REDACTED_PRIVATE_KEY]",
    "cnpj": "[REDACTED_CNPJ]",
    "cpf": "[REDACTED_CPF]",
    "email": "[REDACTED_EMAIL]",
    "phone": "[REDACTED_PHONE]",
}


def mask_pii(value: str) -> str:
    masked = value
    for name, pattern in _PATTERNS:
        if name == "secret_assignment":
            masked = pattern.sub(r"\1=[REDACTED]", masked)
            continue
        masked = pattern.sub(_MASK_LABELS[name], masked)
    return masked


def find_sensitive_patterns(value: str) -> tuple[str, ...]:
    found: list[str] = []
    for name, pattern in _PATTERNS:
        if pattern.search(value) and name not in found:
            found.append(name)
    return tuple(found)


def contains_sensitive_term(value: str, terms: tuple[str, ...]) -> bool:
    folded = value.casefold()
    return any(len(term.strip()) >= 4 and term.strip().casefold() in folded for term in terms)
