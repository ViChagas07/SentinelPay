from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis

from paysentineliq.application.ports.analysis import AnalysisRepositoryPort
from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisRecord,
    AnalysisStatus,
)
from paysentineliq.infrastructure.cache.analysis_cancellation import (
    RedisAnalysisCancellation,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeRedis:
    def __init__(self, *, exists: int = 0, fail: bool = False) -> None:
        self._exists = exists
        self._fail = fail
        self.deleted: list[str] = []
        self.set_calls: list[tuple[str, str, int]] = []

    async def exists(self, key: str) -> int:
        if self._fail:
            raise ConnectionError("redis down")
        return self._exists

    async def set(self, key: str, value: str, *, ex: int) -> None:
        self.set_calls.append((key, value, ex))

    async def delete(self, key: str) -> None:
        self.deleted.append(key)


class FakeRepository:
    def __init__(self, status: AnalysisStatus | None) -> None:
        self.status = status
        self.calls = 0

    async def get(self, analysis_id: UUID) -> AnalysisRecord | None:
        self.calls += 1
        if self.status is None:
            return None
        return AnalysisRecord(
            id=analysis_id,
            owner_id=uuid4(),
            document_id=uuid4(),
            document_type=AnalysisDocumentType.BOLETO,
            status=self.status,
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
        )


def _cancellation(
    redis: FakeRedis,
    repository: FakeRepository,
    *,
    fallback_interval_seconds: float = 0,
) -> RedisAnalysisCancellation:
    return RedisAnalysisCancellation(
        cast(Redis, redis),
        fallback=cast(AnalysisRepositoryPort, repository),
        fallback_interval_seconds=fallback_interval_seconds,
    )


async def test_redis_flag_wins_without_querying_the_database() -> None:
    repository = FakeRepository(AnalysisStatus.RUNNING)
    cancellation = _cancellation(FakeRedis(exists=1), repository)

    assert await cancellation.is_cancelled(uuid4()) is True
    assert repository.calls == 0


async def test_database_status_is_a_fallback_when_the_flag_is_missing() -> None:
    repository = FakeRepository(AnalysisStatus.CANCELLING)
    cancellation = _cancellation(FakeRedis(exists=0), repository)

    assert await cancellation.is_cancelled(uuid4()) is True
    assert repository.calls == 1


async def test_database_status_is_a_fallback_when_redis_fails() -> None:
    repository = FakeRepository(AnalysisStatus.CANCELLING)
    cancellation = _cancellation(FakeRedis(fail=True), repository)

    assert await cancellation.is_cancelled(uuid4()) is True
    assert repository.calls == 1


async def test_running_status_is_not_cancelled() -> None:
    repository = FakeRepository(AnalysisStatus.RUNNING)
    cancellation = _cancellation(FakeRedis(exists=0), repository)

    assert await cancellation.is_cancelled(uuid4()) is False


async def test_fallback_checks_are_throttled() -> None:
    repository = FakeRepository(AnalysisStatus.CANCELLING)
    cancellation = _cancellation(
        FakeRedis(exists=0),
        repository,
        fallback_interval_seconds=60,
    )
    analysis_id = uuid4()

    assert await cancellation.is_cancelled(analysis_id) is True
    assert await cancellation.is_cancelled(analysis_id) is False
    assert repository.calls == 1


async def test_request_and_clear_use_the_prefixed_key() -> None:
    redis = FakeRedis()
    cancellation = _cancellation(redis, FakeRepository(None))
    analysis_id = uuid4()
    key = f"analysis:cancel:{analysis_id}"

    await cancellation.request(analysis_id)
    await cancellation.clear(analysis_id)

    assert redis.set_calls == [(key, "1", 86_400)]
    assert redis.deleted == [key]
