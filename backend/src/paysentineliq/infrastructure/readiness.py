import logging

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from paysentineliq.application.ports.readiness import ReadinessStatus

_logger = logging.getLogger("paysentineliq")


class SqlAlchemyRedisReadinessChecker:
    def __init__(self, engine: AsyncEngine, redis: Redis) -> None:
        self._engine = engine
        self._redis = redis

    async def check(self) -> ReadinessStatus:
        database_ok = True
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            database_ok = False
            _logger.warning("readiness_postgres_failed")

        cache_ok = True
        try:
            await self._redis.ping()
        except Exception:
            cache_ok = False
            _logger.warning("readiness_redis_failed")

        return ReadinessStatus(database=database_ok, cache=cache_ok)
