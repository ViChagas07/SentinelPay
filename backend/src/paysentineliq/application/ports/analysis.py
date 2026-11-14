from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisRecord,
    AnalysisReport,
    AnalysisStatus,
    DegradationFlag,
)
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.notification import Notification
from paysentineliq.domain.scoring import RiskBand


@dataclass(frozen=True, slots=True)
class AnalysisDocument:
    id: UUID
    owner_id: UUID
    kind: DocumentKind
    s3_key: str
    content_type: str
    size: int


class AnalysisDocumentPort(Protocol):
    async def get(self, document_id: UUID) -> AnalysisDocument | None: ...

    async def read(self, document: AnalysisDocument) -> bytes: ...


class AnalysisLookupPort(Protocol):
    async def find_by_idempotency(
        self,
        owner_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRecord | None: ...

    async def count_active_for_owner(self, owner_id: UUID) -> int: ...


class AnalysisRepositoryPort(AnalysisLookupPort, Protocol):
    async def create(
        self,
        record: AnalysisRecord,
        *,
        event: AnalysisEvent | None = None,
    ) -> None: ...

    async def update_state(
        self,
        analysis_id: UUID,
        *,
        status: AnalysisStatus,
        state: Mapping[str, object],
        degradation_flags: tuple[DegradationFlag, ...],
        event: AnalysisEvent | None = None,
    ) -> bool: ...

    async def complete(
        self,
        analysis_id: UUID,
        *,
        score: int,
        band: RiskBand,
        rule_set_version: str,
        model_versions: Mapping[str, str],
        degradation_flags: tuple[DegradationFlag, ...],
        state: Mapping[str, object],
        report_s3_key: str,
        event: AnalysisEvent | None = None,
        notifications: tuple[Notification, ...] = (),
    ) -> bool: ...

    async def fail(
        self,
        analysis_id: UUID,
        *,
        error_code: str,
        state: Mapping[str, object],
        event: AnalysisEvent | None = None,
        notifications: tuple[Notification, ...] = (),
    ) -> bool: ...

    async def claim_for_processing(
        self,
        analysis_id: UUID,
        *,
        task_id: str,
        lease_seconds: int,
        event: AnalysisEvent | None = None,
    ) -> AnalysisRecord | None: ...

    async def get(self, analysis_id: UUID) -> AnalysisRecord | None: ...

    async def list_stale_processing(
        self,
        before: datetime,
    ) -> tuple[AnalysisRecord, ...]: ...


class AnalysisEventPort(Protocol):
    async def append(self, event: AnalysisEvent) -> None: ...


class AnalysisOrchestratorPort(Protocol):
    async def run(
        self,
        *,
        analysis_id: UUID,
        document: AnalysisDocument,
        data: bytes,
        locale: str = "pt",
    ) -> AnalysisReport: ...


def document_type_for(kind: DocumentKind) -> AnalysisDocumentType | None:
    if kind is DocumentKind.BANK_SLIP:
        return AnalysisDocumentType.BOLETO
    if kind is DocumentKind.PAYSLIP:
        return AnalysisDocumentType.PAYSLIP
    return None
