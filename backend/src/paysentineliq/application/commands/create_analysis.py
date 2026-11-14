import asyncio
import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

from paysentineliq.application.commands.documents import DocumentPreparer
from paysentineliq.application.errors import (
    AnalysisQuotaExceededError,
    IdempotencyConflictError,
    InvalidIdempotencyKeyError,
    UnsupportedDocumentError,
)
from paysentineliq.application.ports.analysis import (
    AnalysisLookupPort,
    document_type_for,
)
from paysentineliq.application.ports.analysis_unit_of_work import AnalysisUnitOfWork
from paysentineliq.application.ports.task_dispatcher import TaskDispatcherPort
from paysentineliq.domain.analysis import (
    AnalysisEvent,
    AnalysisEventType,
    AnalysisRecord,
    AnalysisStatus,
)
from paysentineliq.domain.document import DocumentKind

_logger = logging.getLogger("paysentineliq")

_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@dataclass(frozen=True, slots=True)
class CreateAnalysisCommand:
    owner_id: UUID
    kind: DocumentKind
    original_name: str | None
    stream: BinaryIO
    idempotency_key: str | None = None
    locale: str = "pt"


@dataclass(frozen=True, slots=True)
class CreatedAnalysis:
    analysis_id: UUID
    document_id: UUID
    status: AnalysisStatus
    replayed: bool = False


def normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if _IDEMPOTENCY_RE.fullmatch(trimmed) is None:
        raise InvalidIdempotencyKeyError()
    return trimmed


class CreateAnalysisHandler:
    def __init__(
        self,
        unit_of_work: AnalysisUnitOfWork,
        preparer: DocumentPreparer,
        lookup: AnalysisLookupPort,
        dispatcher: TaskDispatcherPort,
        *,
        max_concurrent_per_user: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_concurrent_per_user <= 0:
            raise ValueError("max_concurrent_per_user must be positive")
        self._unit_of_work = unit_of_work
        self._preparer = preparer
        self._lookup = lookup
        self._dispatcher = dispatcher
        self._max_concurrent = max_concurrent_per_user
        self._clock = clock or (lambda: datetime.now(UTC))

    async def handle(self, command: CreateAnalysisCommand) -> CreatedAnalysis:
        document_type = document_type_for(command.kind)
        if document_type is None:
            raise UnsupportedDocumentError()
        idempotency_key = normalize_idempotency_key(command.idempotency_key)
        inspected = await self._preparer.inspect(command.stream)
        request_hash = hashlib.sha256(
            f"{command.kind.value}:{inspected.sha256}".encode(),
        ).hexdigest()

        if idempotency_key is not None:
            existing = await self._lookup.find_by_idempotency(
                command.owner_id,
                idempotency_key,
            )
            if existing is not None:
                self._assert_same_request(existing.idempotency_request_hash, request_hash)
                return CreatedAnalysis(
                    analysis_id=existing.id,
                    document_id=existing.document_id,
                    status=existing.status,
                    replayed=True,
                )

        active = await self._lookup.count_active_for_owner(command.owner_id)
        if active >= self._max_concurrent:
            raise AnalysisQuotaExceededError()

        analysis_id = uuid4()
        document = await self._preparer.prepare(
            owner_id=command.owner_id,
            kind=command.kind,
            original_name=command.original_name,
            stream=command.stream,
            analysis_id=analysis_id,
            inspected=inspected,
        )
        now = self._clock()
        record = AnalysisRecord(
            id=analysis_id,
            owner_id=command.owner_id,
            document_id=document.id,
            document_type=document_type,
            status=AnalysisStatus.QUEUED,
            score=None,
            band=None,
            rule_set_version=None,
            model_versions={},
            degradation_flags=(),
            state={},
            report_s3_key=None,
            error_code=None,
            created_at=now,
            updated_at=now,
            idempotency_key=idempotency_key,
            idempotency_request_hash=request_hash if idempotency_key else None,
        )
        replay: AnalysisRecord | None = None
        try:
            async with self._unit_of_work as uow:
                if idempotency_key is not None:
                    await uow.analyses.lock_idempotency(command.owner_id, idempotency_key)
                    replay = await uow.analyses.find_by_idempotency(
                        command.owner_id,
                        idempotency_key,
                    )
                    if replay is not None:
                        self._assert_same_request(replay.idempotency_request_hash, request_hash)
                if replay is None:
                    await uow.analyses.lock_quota(command.owner_id)
                    if (
                        await uow.analyses.count_active_for_owner(command.owner_id)
                        >= self._max_concurrent
                    ):
                        raise AnalysisQuotaExceededError()
                    await uow.documents.add(document)
                    await uow.analyses.add(
                        record,
                        event=AnalysisEvent(
                            analysis_id=analysis_id,
                            event_type=AnalysisEventType.QUEUED,
                            payload={"document_id": str(document.id)},
                        ),
                    )
                    await uow.commit()
                else:
                    await uow.rollback()
        except Exception:
            await self._discard(document.s3_key)
            raise

        if replay is not None:
            await self._discard(document.s3_key)
            return CreatedAnalysis(
                analysis_id=replay.id,
                document_id=replay.document_id,
                status=replay.status,
                replayed=True,
            )

        try:
            await asyncio.to_thread(
                self._dispatcher.dispatch_analysis,
                analysis_id,
                locale=command.locale,
            )
        except Exception:
            _logger.error("analysis_dispatch_failed")
            raise

        return CreatedAnalysis(
            analysis_id=analysis_id,
            document_id=document.id,
            status=AnalysisStatus.QUEUED,
        )

    async def _discard(self, s3_key: str) -> None:
        try:
            await self._preparer.discard(s3_key)
        except Exception:
            _logger.error("storage_compensation_failed")

    @staticmethod
    def _assert_same_request(
        stored_hash: str | None,
        request_hash: str,
    ) -> None:
        if stored_hash != request_hash:
            raise IdempotencyConflictError()
