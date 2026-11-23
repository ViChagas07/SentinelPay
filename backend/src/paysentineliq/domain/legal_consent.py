from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class LegalDocument(StrEnum):
    TERMS = "terms"
    PRIVACY = "privacy"


@dataclass(frozen=True, slots=True)
class LegalConsent:
    user_id: UUID
    document: LegalDocument
    version: str
    accepted_at: datetime
    source: str
    created_ip: str | None
    created_user_agent: str | None
