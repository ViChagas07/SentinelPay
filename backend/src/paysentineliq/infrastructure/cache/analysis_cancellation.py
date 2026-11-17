import logging
import time
from uuid import UUID

from redis.asyncio import Redis

from paysentineliq.application.ports.analysis import AnalysisRepositoryPort
from paysentineliq.domain.analysis import AnalysisStatus

_logger = logging.getLogger("paysentineliq")

_KEY_PREFIX = "analysis:cancel:"
_DEFAULT_TTL_SECONDS = 86_400
_DEFAULT_FALLBACK_INTERVAL_SECONDS = 2.0


class RedisAnalysisCancellation:
    def __init__(
        self,
        redis: Redis,
        *,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        fallback: AnalysisRepositoryPort | None = None,
        fallback_interval_seconds: float = _DEFAULT_FALLBACK_INTERVAL_SECONDS,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if fallback_interval_seconds < 0:
            raise ValueError("fallback_interval_seconds must not be negative")
        self._redis = redis
        self._ttl_seconds = ttl_seconds
        self._fallback = fallback
        self._fallback_interval_seconds = fallback_interval_seconds
        self._last_fallback_check: dict[UUID, float] = {}

    @staticmethod
    def _key(analysis_id: UUID) -> str:
        return f"{_KEY_PREFIX}{analysis_id}"

    async def request(self, analysis_id: UUID) -> None:
        try:
            await self._redis.set(self._key(analysis_id), "1", ex=self._ttl_seconds)
        except Exception:
            _logger.warning("analysis_cancel_flag_write_failed")

    async def clear(self, analysis_id: UUID) -> None:
        self._last_fallback_check.pop(analysis_id, None)
        try:
            await self._redis.delete(self._key(analysis_id))
        except Exception:
            _logger.warning("analysis_cancel_flag_clear_failed")

    async def is_cancelled(self, analysis_id: UUID) -> bool:
        try:
            if await self._redis.exists(self._key(analysis_id)):
                return True
        except Exception:
            _logger.warning("analysis_cancel_flag_read_failed")
            self._last_fallback_check.pop(analysis_id, None)
        if self._fallback is None:
            return False
        now = time.monotonic()
        last = self._last_fallback_check.get(analysis_id)
        if last is not None and now - last < self._fallback_interval_seconds:
            return False
        self._last_fallback_check[analysis_id] = now
        record = await self._fallback.get(analysis_id)
        return record is not None and record.status in (
            AnalysisStatus.CANCELLING,
            AnalysisStatus.CANCELLED,
        )
