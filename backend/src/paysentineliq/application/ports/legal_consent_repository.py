from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from paysentineliq.domain.legal_consent import LegalConsent


class LegalConsentRepository(Protocol):
    async def add_many(self, consents: Sequence[LegalConsent]) -> None: ...

    async def has_version(self, user_id: UUID, version: str) -> bool: ...
