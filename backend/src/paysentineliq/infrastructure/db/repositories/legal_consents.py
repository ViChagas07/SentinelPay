from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paysentineliq.domain.legal_consent import LegalConsent
from paysentineliq.infrastructure.db.models import LegalConsentModel


class SqlAlchemyLegalConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, consents: Sequence[LegalConsent]) -> None:
        self._session.add_all(
            [
                LegalConsentModel(
                    user_id=consent.user_id,
                    document=consent.document.value,
                    version=consent.version,
                    accepted_at=consent.accepted_at,
                    source=consent.source,
                    created_ip=consent.created_ip,
                    created_user_agent=consent.created_user_agent,
                )
                for consent in consents
            ]
        )
        await self._session.flush()

    async def has_version(self, user_id: UUID, version: str) -> bool:
        existing = await self._session.scalar(
            select(LegalConsentModel.id).where(
                LegalConsentModel.user_id == user_id,
                LegalConsentModel.version == version,
            )
        )
        return existing is not None
