import hashlib
import hmac
import re
from collections.abc import Mapping, Sequence
from typing import Any

from paysentineliq.application.security.redaction import mask_pii

_DIGIT_RUN_RE = re.compile(r"[0-9][0-9\s.\-]{40,90}")
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
)
_CPF_UNFORMATTED_RE = re.compile(r"\b\d{11}\b")
_CPF_SPACED_RE = re.compile(r"\b\d{3}[\s.-]\d{3}[\s.-]\d{3}[\s.-]\d{2}\b")
_CNPJ_UNFORMATTED_RE = re.compile(r"\b\d{14}\b")
_CNPJ_SPACED_RE = re.compile(
    r"\b\d{2}[\s.-]\d{3}[\s.-]\d{3}[\s.-]\d{4}[\s.-]\d{2}\b",
)
_PIX_RANDOM_RE = re.compile(r"\b[0-9a-fA-F]{32}\b")
_PHONE_UNFORMATTED_RE = re.compile(r"\b\d{10}\b")
_INTERNATIONAL_PHONE_RE = re.compile(
    r"(?<!\w)\+\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{3,5}[\s.-]?\d{3,5}(?!\w)",
)
_LOCAL_PHONE_RE = re.compile(r"\b\d{3}[\s.-]\d{3}[\s.-]\d{3,4}\b")
_MONEY_BRL_RE = re.compile(r"\bR\$\s*[0-9][0-9.,]*", re.IGNORECASE)
_MONEY_LABEL_RE = re.compile(
    r"(?i)\b(valor|montante|total|importe|amount|salary|salario|salario|sueldo)\b"
    r"\s*[:=]?\s*(?:R\$\s*)?[0-9][0-9.,]*",
)
_CEP_RE = re.compile(r"\b\d{5}-?\d{3}\b")
_ADDRESS_LABEL_RE = re.compile(
    r"(?im)^\s*(endereco|endereço|address|direccion|dirección|logradouro|"
    r"rua|avenida|av\.|street|calle)\b[^\n]*$",
)
_ADDRESS_INLINE_RE = re.compile(
    r"(?i)\b(endereco|endereço|address|direccion|dirección|logradouro)\b"
    r"\s*[:=]\s*[^\n;]+",
)
_NAME_LABEL_RE = re.compile(
    r"(?im)^\s*(nome|nombre|name|full name|raz[aã]o social|razon social|"
    r"titular|pagador|sacado|benefici[aá]rio|beneficiary|cedente|"
    r"empregado|funcion[aá]rio|employee|employer|payer|payee|customer|"
    r"cliente|holder)\b[^\n]*$",
)
_NAME_INLINE_RE = re.compile(
    r"(?i)(?<!model )(?<!file )(?<!prompt )"
    r"\b(nome|nombre|name|titular|pagador|sacado|benefici[aá]rio|beneficiary|"
    r"cedente|empregado|funcion[aá]rio|employee|employer|payer|payee|"
    r"customer|cliente|holder)\b"
    r"\s*[:=]\s*[^\n,;]+",
)
_HONORIFIC_NAME_RE = re.compile(
    r"\b(?:Sr\.|Sra\.|Srta\.|Dr\.|Dra\.)\s+"
    r"[A-ZÀ-Ý][\wÀ-ÿ]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]+)*",
)
_PIX_LABEL_RE = re.compile(
    r"(?i)\b(chave\s+pix|pix|clave\s+pix)\b\s*[:=]\s*[^\s,;]+",
)

_RAW_TEXT_KEYS = frozenset(
    {
        "content",
        "text",
        "document_text",
        "ocr_text",
        "raw_text",
        "excerpt",
        "document_excerpt",
        "justification",
        "reason",
        "message",
        "prompt",
        "input_text",
        "output_text",
        "inconsistencies",
        "findings",
        "rag_snippets",
        "snippets",
    },
)
_NAME_KEYS = frozenset(
    {
        "name",
        "full_name",
        "person_name",
        "payer_name",
        "payee_name",
        "beneficiary_name",
        "employee_name",
        "employer_name",
        "customer_name",
        "holder_name",
        "nome",
        "nombre",
        "razao_social",
        "razon_social",
        "sacado",
        "cedente",
        "pagador",
        "beneficiario",
        "beneficiary",
        "payer",
        "payee",
        "employee",
        "employer",
        "funcionario",
        "empregado",
        "titular",
        "cliente",
        "customer",
    },
)
_DOCUMENT_KEYS = frozenset(
    {
        "cpf",
        "cnpj",
        "tax_id",
        "document",
        "document_number",
        "rg",
        "cnh",
        "passport",
        "matricula",
    },
)
_MONEY_KEYS = frozenset(
    {
        "value",
        "amount",
        "total",
        "salary",
        "wage",
        "net",
        "gross",
        "discount",
        "inss",
        "irrf",
        "fgts",
        "valor",
        "salario",
        "liquido",
        "bruto",
        "desconto",
        "provento",
        "importe",
        "montante",
        "sueldo",
    },
)
_LINE_KEYS = frozenset(
    {
        "digitable_line",
        "linha_digitavel",
        "barcode",
        "codigo_barras",
        "payment_line",
        "barcode_value",
    },
)
_EMAIL_KEYS = frozenset({"email", "e_mail", "correo"})
_PHONE_KEYS = frozenset({"phone", "telefone", "celular", "telefono", "mobile"})
_PIX_KEYS = frozenset({"pix", "pix_key", "chave_pix", "clave_pix"})
_ADDRESS_KEYS = frozenset(
    {
        "address",
        "endereco",
        "logradouro",
        "street",
        "direccion",
        "cep",
        "zip",
        "zip_code",
        "postal_code",
        "bairro",
        "neighborhood",
        "cidade",
        "city",
        "estado",
        "state",
        "uf",
    },
)
_USER_ID_KEYS = frozenset(
    {"user_id", "owner_id", "subject", "sub", "user", "owner", "usuario"},
)
_SECRET_KEYS = frozenset(
    {"token", "access_token", "refresh_token", "api_key", "secret", "password"},
)
_SAFE_KEYS = frozenset(
    {
        "id",
        "analysis_id",
        "document_id",
        "request_id",
        "trace_id",
        "span_id",
        "rule_id",
        "message_key",
        "model",
        "model_version",
        "prompt_version",
        "band",
        "document_type",
        "language",
        "severity",
        "outcome",
        "status",
        "latency_ms",
        "chars",
        "length",
        "sha256",
        "hash",
        "as_type",
        "verdict_reason",
    },
)
_SAFE_NAME_SUFFIXES = frozenset(
    {"model_name", "prompt_name", "rule_name", "field_name"},
)


class ObservabilityMasker:
    def __init__(self, *, hash_secret: str = "") -> None:
        self._hash_secret = hash_secret.encode("utf-8")

    def mask_payload(self, data: Any) -> Any:
        return self._mask_value(data, key=None)

    def mask_for_langfuse(self, *, data: Any, **_: Any) -> Any:
        return self.mask_payload(data)

    def mask_text(self, value: str) -> str:
        masked = _DIGIT_RUN_RE.sub(_mask_digit_run, value)
        masked = mask_pii(masked)
        masked = _PIX_LABEL_RE.sub(lambda match: f"{match.group(1)}: [REDACTED_PIX_KEY]", masked)
        masked = _ADDRESS_LABEL_RE.sub("[REDACTED_ADDRESS]", masked)
        masked = _ADDRESS_INLINE_RE.sub(
            lambda match: f"{match.group(1)}: [REDACTED_ADDRESS]",
            masked,
        )
        masked = _NAME_LABEL_RE.sub("[REDACTED_NAME]", masked)
        masked = _NAME_INLINE_RE.sub(
            lambda match: f"{match.group(1)}: [REDACTED_NAME]",
            masked,
        )
        masked = _HONORIFIC_NAME_RE.sub("[REDACTED_NAME]", masked)
        masked = _MONEY_BRL_RE.sub("[REDACTED_MONEY]", masked)
        masked = _MONEY_LABEL_RE.sub(
            lambda match: f"{match.group(1)}: [REDACTED_MONEY]",
            masked,
        )
        masked = _CNPJ_UNFORMATTED_RE.sub("[REDACTED_CNPJ]", masked)
        masked = _CNPJ_SPACED_RE.sub("[REDACTED_CNPJ]", masked)
        masked = _CPF_UNFORMATTED_RE.sub("[REDACTED_CPF]", masked)
        masked = _CPF_SPACED_RE.sub("[REDACTED_CPF]", masked)
        masked = _PHONE_UNFORMATTED_RE.sub("[REDACTED_PHONE]", masked)
        masked = _INTERNATIONAL_PHONE_RE.sub("[REDACTED_PHONE]", masked)
        masked = _LOCAL_PHONE_RE.sub("[REDACTED_PHONE]", masked)
        masked = _CEP_RE.sub("[REDACTED_CEP]", masked)
        masked = _UUID_RE.sub("[REDACTED_IDENTIFIER]", masked)
        masked = _PIX_RANDOM_RE.sub("[REDACTED_PIX_KEY]", masked)
        return masked

    def hash_identifier(self, value: str) -> str:
        return f"sha256:{self._digest(value)}"

    def _mask_value(self, value: Any, *, key: str | None) -> Any:
        normalized = _normalize_key(key) if key is not None else ""
        if normalized:
            masked = self._mask_keyed_value(value, normalized)
            if masked is not _UNCHANGED:
                return masked
        if isinstance(value, Mapping):
            return {
                str(item_key): self._mask_value(item_value, key=str(item_key))
                for item_key, item_value in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._mask_value(item, key=key) for item in value]
        if isinstance(value, (bytes, bytearray, memoryview)):
            return "[REDACTED_BINARY]"
        if isinstance(value, str):
            return self.mask_text(value)
        if value is None or isinstance(value, (bool, int, float)):
            return value
        text = str(value)
        return {"sha256": self._digest(text), "length": len(text)}

    def _mask_keyed_value(self, value: Any, key: str) -> Any:
        if key in _USER_ID_KEYS or key.endswith("_user_id"):
            return self.hash_identifier(str(value))
        if key in _RAW_TEXT_KEYS or key.endswith(("_text", "_excerpt", "_content")):
            return self._text_fingerprint(value)
        if key in _SECRET_KEYS or key.endswith(("_token", "_secret", "_password")):
            return "[REDACTED_SECRET]"
        if key in _NAME_KEYS or (key.endswith("_name") and key not in _SAFE_NAME_SUFFIXES):
            return "[REDACTED_NAME]"
        if key in _DOCUMENT_KEYS:
            return "[REDACTED_DOCUMENT]"
        if key in _MONEY_KEYS:
            return "[REDACTED_MONEY]"
        if key in _LINE_KEYS:
            return "[REDACTED_LINE]"
        if key in _EMAIL_KEYS:
            return "[REDACTED_EMAIL]"
        if key in _PHONE_KEYS:
            return "[REDACTED_PHONE]"
        if key in _PIX_KEYS:
            return "[REDACTED_PIX_KEY]"
        if key in _ADDRESS_KEYS:
            return "[REDACTED_ADDRESS]"
        if key in _SAFE_KEYS or key.endswith("_id"):
            return value
        if key.endswith(("_hash", "_sha256")):
            return value
        return _UNCHANGED

    def _text_fingerprint(self, value: Any) -> Any:
        if isinstance(value, str):
            return {"sha256": self._digest(value), "length": len(value)}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [self._text_fingerprint(item) for item in value]
        return {"sha256": self._digest(str(value)), "length": len(str(value))}

    def _digest(self, value: str) -> str:
        data = value.encode("utf-8")
        if self._hash_secret:
            return hmac.new(self._hash_secret, data, hashlib.sha256).hexdigest()
        return hashlib.sha256(data).hexdigest()


_UNCHANGED = object()


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")


def _mask_digit_run(match: re.Match[str]) -> str:
    digits = sum(character.isdigit() for character in match.group(0))
    if digits in {44, 47, 48}:
        return "[REDACTED_LINE]"
    return match.group(0)
