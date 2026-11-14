import asyncio
import logging
from typing import Protocol

import httpx

from paysentineliq.infrastructure.observability.metrics import (
    KNOWN_QUEUES,
    PlatformMetrics,
)

_logger = logging.getLogger("paysentineliq")


class QueueDepthProvider(Protocol):
    async def fetch(self) -> dict[str, int]: ...


class RabbitMqQueueDepthProvider:
    def __init__(
        self,
        *,
        base_url: str,
        username: str = "",
        password: str = "",
        timeout_seconds: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._timeout = timeout_seconds
        self._transport = transport

    async def fetch(self) -> dict[str, int]:
        auth = httpx.BasicAuth(self._username, self._password) if self._username else None
        async with httpx.AsyncClient(
            base_url=self._base_url,
            auth=auth,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.get("/api/queues/%2F")
            response.raise_for_status()
            payload = response.json()
        depths: dict[str, int] = {}
        if not isinstance(payload, list):
            return depths
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            messages = item.get("messages")
            if isinstance(name, str) and name in KNOWN_QUEUES and isinstance(messages, int):
                depths[name] = max(0, messages)
        return depths


class QueueDepthMonitor:
    def __init__(
        self,
        provider: QueueDepthProvider,
        metrics: PlatformMetrics,
        *,
        interval_seconds: float,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._provider = provider
        self._metrics = metrics
        self._interval = interval_seconds
        self._last_failed = False

    async def run(self) -> None:
        while True:
            await self.refresh_once()
            await asyncio.sleep(self._interval)

    async def refresh_once(self) -> None:
        try:
            depths = await self._provider.fetch()
        except Exception:
            if not self._last_failed:
                _logger.warning("queue_depth_refresh_failed")
            self._last_failed = True
            return
        self._last_failed = False
        for queue in KNOWN_QUEUES:
            self._metrics.set_queue_depth(queue, depths.get(queue, 0))
