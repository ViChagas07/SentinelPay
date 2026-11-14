import hashlib
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.commands.create_analysis import (
    CreateAnalysisCommand,
    CreateAnalysisHandler,
    normalize_idempotency_key,
)
from paysentineliq.application.commands.documents import DocumentPreparer
from paysentineliq.application.errors import (
    AnalysisQuotaExceededError,
    IdempotencyConflictError,
    InvalidIdempotencyKeyError,
    TaskDispatchError,
)
from paysentineliq.application.ports.document_inspector import InspectedDocument
from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisRecord,
    AnalysisStatus,
)
from paysentineliq.domain.document import Document, DocumentKind

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_OWNER = uuid4()


class FakeInspector:
    async def inspect(
        self,
        stream: Any,
        *,
        max_bytes: int,
        max_pdf_pages: int,
    ) -> InspectedDocument:
        data = stream.read()
        stream.seek(0)
        return InspectedDocument(
            extension="pdf",
            content_type="application/pdf",
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            page_count=1,
        )


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[dict[str, Any]] = []
        self.deleted: list[str] = []

    async def put(
        self,
        key: str,
        stream: Any,
        *,
        content_type: str,
        size: int,
        metadata: Any = None,
    ) -> None:
        stream.seek(0)
        self.puts.append({"key": key, "data": stream.read(), "metadata": metadata})

    async def delete(self, key: str) -> None:
        self.deleted.append(key)

    def get_stream(self, key: str) -> Any:
        raise NotImplementedError

    async def presigned_get_url(self, key: str, *, expires_in: int) -> str:
        raise NotImplementedError


class FakeStore:
    def __init__(self) -> None:
        self.records: dict[UUID, AnalysisRecord] = {}
        self.events: list[AnalysisEvent] = []
        self.documents: list[Document] = []
        self.on_lock_idempotency: Any = None

    def active_count(self, owner_id: UUID) -> int:
        return sum(
            1
            for record in self.records.values()
            if record.owner_id == owner_id
            and record.status in (AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING)
        )


class FakeDocuments:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def add(self, document: Document) -> Document:
        self._store.documents.append(document)
        return document

    async def get_by_id_for_owner(
        self,
        document_id: UUID,
        owner_id: UUID,
    ) -> Document | None:
        return next(
            (
                document
                for document in self._store.documents
                if document.id == document_id and document.owner_id == owner_id
            ),
            None,
        )


class FakeCreationRepo:
    def __init__(self, store: FakeStore) -> None:
        self._store = store
        self.idempotency_locks: list[tuple[UUID, str]] = []
        self.quota_locks: list[UUID] = []

    async def lock_idempotency(self, owner_id: UUID, idempotency_key: str) -> None:
        self.idempotency_locks.append((owner_id, idempotency_key))
        if self._store.on_lock_idempotency is not None:
            self._store.on_lock_idempotency()

    async def find_by_idempotency(
        self,
        owner_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRecord | None:
        return next(
            (
                record
                for record in self._store.records.values()
                if record.owner_id == owner_id and record.idempotency_key == idempotency_key
            ),
            None,
        )

    async def lock_quota(self, owner_id: UUID) -> None:
        self.quota_locks.append(owner_id)

    async def count_active_for_owner(self, owner_id: UUID) -> int:
        return self._store.active_count(owner_id)

    async def add(
        self,
        record: AnalysisRecord,
        *,
        event: AnalysisEvent | None = None,
    ) -> None:
        self._store.records[record.id] = record
        if event is not None:
            self._store.events.append(event)


class FakeLookup:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def find_by_idempotency(
        self,
        owner_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRecord | None:
        return next(
            (
                record
                for record in self._store.records.values()
                if record.owner_id == owner_id and record.idempotency_key == idempotency_key
            ),
            None,
        )

    async def count_active_for_owner(self, owner_id: UUID) -> int:
        return self._store.active_count(owner_id)


class FakeUoW:
    def __init__(self, store: FakeStore) -> None:
        self.documents = FakeDocuments(store)
        self.analyses = FakeCreationRepo(store)
        self.committed = False
        self.rolled_back = False
        self.fail_commit = False

    async def __aenter__(self) -> "FakeUoW":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError("commit failed")
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeDispatcher:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.dispatched: list[tuple[UUID, str]] = []
        self._error = error

    def dispatch_analysis(self, analysis_id: UUID, *, locale: str = "pt") -> None:
        if self._error is not None:
            raise self._error
        self.dispatched.append((analysis_id, locale))

    def dispatch_notification(self, notification_id: UUID) -> None:
        return None


def _request_hash(data: bytes) -> str:
    return hashlib.sha256(f"bank_slip:{hashlib.sha256(data).hexdigest()}".encode()).hexdigest()


def _existing(
    *,
    idempotency_key: str,
    request_hash: str,
    owner_id: UUID = _OWNER,
    status: AnalysisStatus = AnalysisStatus.QUEUED,
) -> AnalysisRecord:
    return AnalysisRecord(
        id=uuid4(),
        owner_id=owner_id,
        document_id=uuid4(),
        document_type=AnalysisDocumentType.BOLETO,
        status=status,
        score=None,
        band=None,
        rule_set_version=None,
        model_versions={},
        degradation_flags=(),
        state={},
        report_s3_key=None,
        error_code=None,
        created_at=_NOW,
        updated_at=_NOW,
        idempotency_key=idempotency_key,
        idempotency_request_hash=request_hash,
    )


def _handler(
    store: FakeStore,
    *,
    max_concurrent: int = 2,
    dispatcher: FakeDispatcher | None = None,
) -> tuple[CreateAnalysisHandler, FakeStorage, FakeUoW, FakeDispatcher]:
    storage = FakeStorage()
    uow = FakeUoW(store)
    fake_dispatcher = dispatcher or FakeDispatcher()
    handler = CreateAnalysisHandler(
        uow,
        DocumentPreparer(
            storage,
            FakeInspector(),
            max_bytes=1024 * 1024,
            max_pdf_pages=10,
            clock=lambda: _NOW,
        ),
        FakeLookup(store),
        fake_dispatcher,
        max_concurrent_per_user=max_concurrent,
        clock=lambda: _NOW,
    )
    return handler, storage, uow, fake_dispatcher


def _command(
    *,
    idempotency_key: str | None = None,
    data: bytes = b"%PDF-1.4 synthetic",
) -> CreateAnalysisCommand:
    return CreateAnalysisCommand(
        owner_id=_OWNER,
        kind=DocumentKind.BANK_SLIP,
        original_name="boleto.pdf",
        stream=BytesIO(data),
        idempotency_key=idempotency_key,
        locale="pt",
    )


async def test_create_persists_document_analysis_and_queued_event() -> None:
    store = FakeStore()
    handler, storage, uow, dispatcher = _handler(store)

    result = await handler.handle(_command(idempotency_key="idem-12345678"))

    assert result.status is AnalysisStatus.QUEUED
    assert result.replayed is False
    assert len(store.records) == 1
    record = next(iter(store.records.values()))
    assert record.status is AnalysisStatus.QUEUED
    assert record.idempotency_key == "idem-12345678"
    assert store.events[0].event_type is AnalysisEventType.QUEUED
    assert len(store.documents) == 1
    assert storage.puts[0]["key"].endswith("/original.pdf")
    assert uow.committed is True
    assert dispatcher.dispatched == [(result.analysis_id, "pt")]


async def test_same_idempotency_key_and_hash_returns_existing_without_upload() -> None:
    data = b"%PDF-1.4 synthetic"
    store = FakeStore()
    existing = _existing(
        idempotency_key="idem-12345678",
        request_hash=_request_hash(data),
    )
    store.records[existing.id] = existing
    handler, storage, _, dispatcher = _handler(store)

    result = await handler.handle(_command(idempotency_key="idem-12345678", data=data))

    assert result.analysis_id == existing.id
    assert result.replayed is True
    assert storage.puts == []
    assert dispatcher.dispatched == []


async def test_same_key_with_different_document_conflicts() -> None:
    store = FakeStore()
    existing = _existing(
        idempotency_key="idem-12345678",
        request_hash="a" * 64,
    )
    store.records[existing.id] = existing
    handler, storage, _, _ = _handler(store)

    with pytest.raises(IdempotencyConflictError):
        await handler.handle(_command(idempotency_key="idem-12345678"))

    assert storage.puts == []


async def test_quota_is_enforced_before_upload() -> None:
    store = FakeStore()
    store.records[uuid4()] = _existing(
        idempotency_key="other-key-123",
        request_hash="b" * 64,
    )
    handler, storage, _, _ = _handler(store, max_concurrent=1)

    with pytest.raises(AnalysisQuotaExceededError):
        await handler.handle(_command(idempotency_key="idem-12345678"))

    assert storage.puts == []


async def test_race_after_upload_replays_existing_and_discards_storage() -> None:
    data = b"%PDF-1.4 synthetic"
    store = FakeStore()
    existing = _existing(
        idempotency_key="idem-12345678",
        request_hash=_request_hash(data),
    )
    store.on_lock_idempotency = lambda: store.records.__setitem__(existing.id, existing)
    handler, storage, _, dispatcher = _handler(store)

    result = await handler.handle(_command(idempotency_key="idem-12345678", data=data))

    assert result.analysis_id == existing.id
    assert result.replayed is True
    assert len(storage.puts) == 1
    assert storage.deleted == [storage.puts[0]["key"]]
    assert dispatcher.dispatched == []


async def test_commit_failure_compensates_storage() -> None:
    store = FakeStore()
    handler, storage, uow, _ = _handler(store)
    uow.fail_commit = True

    with pytest.raises(RuntimeError):
        await handler.handle(_command())

    assert storage.deleted == [storage.puts[0]["key"]]


async def test_dispatch_failure_is_reported_after_commit() -> None:
    store = FakeStore()
    dispatcher = FakeDispatcher(error=TaskDispatchError())
    handler, _, uow, _ = _handler(store, dispatcher=dispatcher)

    with pytest.raises(TaskDispatchError):
        await handler.handle(_command())

    assert uow.committed is True
    assert len(store.records) == 1


@pytest.mark.parametrize("key", ["short", "bad key with spaces", "x" * 129])
def test_invalid_idempotency_key_is_rejected(key: str) -> None:
    with pytest.raises(InvalidIdempotencyKeyError):
        normalize_idempotency_key(key)


def test_empty_idempotency_key_is_treated_as_absent() -> None:
    assert normalize_idempotency_key("") is None
    assert normalize_idempotency_key(None) is None
