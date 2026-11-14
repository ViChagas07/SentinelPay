from typing import Any, cast

import httpcore
import httpx
import pytest

from paysentineliq.application.errors import SSRFBlockedError
from paysentineliq.infrastructure.security.ssrf import (
    PinnedNetworkBackend,
    SafeHttpClient,
    SSRFGuard,
)


async def _public_resolver(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


async def _private_resolver(host: str, port: int) -> list[str]:
    return ["127.0.0.1"]


def _guard() -> SSRFGuard:
    async def resolver(host: str, port: int) -> list[str]:
        if host == "127.0.0.1":
            return await _private_resolver(host, port)
        return await _public_resolver(host, port)

    return SSRFGuard(require_https=True, resolver=resolver)


class RedirectTransport(httpx.AsyncBaseTransport):
    def __init__(self, location: str) -> None:
        self.location = location
        self.calls: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": self.location},
            request=request,
        )


class SequenceTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if len(self.calls) == 1:
            return httpx.Response(
                302,
                headers={"location": "https://public.example/next"},
                request=request,
            )
        return httpx.Response(200, content=b"ok", request=request)


@pytest.mark.unit
async def test_redirect_to_private_ip_is_blocked() -> None:
    transport = RedirectTransport("https://127.0.0.1/secret")
    client = SafeHttpClient(
        _guard(),
        transport_factory=lambda pinned_ip: transport,
    )

    with pytest.raises(SSRFBlockedError):
        await client.request("GET", "https://public.example/start")

    assert transport.calls == ["https://public.example/start"]


@pytest.mark.unit
async def test_safe_redirect_to_public_ip_is_followed() -> None:
    transport = SequenceTransport()
    client = SafeHttpClient(
        _guard(),
        transport_factory=lambda pinned_ip: transport,
    )

    response = await client.request("GET", "https://public.example/start")

    assert response.status_code == 200
    assert response.text == "ok"
    assert transport.calls == [
        "https://public.example/start",
        "https://public.example/next",
    ]


class RecordingBackend:
    def __init__(self) -> None:
        self.host: str | None = None

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> object:
        self.host = host
        return object()

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Any = None,
    ) -> object:
        return object()

    async def sleep(self, seconds: float) -> None:
        return None


@pytest.mark.unit
async def test_pinned_backend_connects_to_validated_ip() -> None:
    recording = RecordingBackend()
    pinned = PinnedNetworkBackend(
        cast(httpcore.AsyncNetworkBackend, recording),
        "93.184.216.34",
    )

    await pinned.connect_tcp("public.example", 443)

    assert recording.host == "93.184.216.34"
