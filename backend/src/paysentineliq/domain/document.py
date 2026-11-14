from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class DocumentKind(StrEnum):
    BANK_SLIP = "bank_slip"
    PAYSLIP = "payslip"
    RECEIPT = "receipt"


@dataclass(frozen=True, slots=True)
class Document:
    id: UUID
    owner_id: UUID
    kind: DocumentKind
    s3_key: str
    sha256: str
    size: int
    content_type: str
    original_name_sanitized: str
    created_at: datetime
