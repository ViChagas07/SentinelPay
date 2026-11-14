import asyncio
import ipaddress
import socket
import ssl
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx

from paysentineliq.application.errors import SSRFBlockedError

Resolver = Callable[[str, int], Awaitable[list[str]]]

_DEFAULT_PORTS = {"http": 80, "https": 443}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_SEE_OTHER_STATUSES = {301, 302, 303}
_BLOCKED_NETWORKS = (
    ipaddress.ip_network("169.254.169.254/32"),
    ipaddress.ip_network("169.254.170.2/32"),
    ipaddress.ip_network("100.100.100.200/32"),
    ipaddress.ip_network("fd00:ec2::254/128"),
)


@dataclass(frozen=True, slots=True)
class ValidatedURL:
    url: str
    host: str
    port: int
    pinned_ip: str


class SSRFGuard:
    def __init__(
        self,
        *,
        require_https: bool,
        allowed_hosts: set[str] | None = None,
        resolver: Resolver | None = None,
    ) -> None:
        self._require_https = require_https
        self._allowed_hosts = {
            host.strip().lower() for host in (allowed_hosts or set()) if host.strip()
        }
        self._resolver = resolver or self._default_resolve

    async def validate_url(self, url: str, *, allow_internal: bool = False) -> ValidatedURL:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        if scheme not in _DEFAULT_PORTS:
            raise SSRFBlockedError()
        if self._require_https and scheme != "https":
            raise SSRFBlockedError()
        if parts.username is not None or parts.password is not None:
            raise SSRFBlockedError()

        host = parts.hostname
        if host is None:
            raise SSRFBlockedError()
        host = host.lower().rstrip(".")

        try:
            port = parts.port or _DEFAULT_PORTS[scheme]
        except ValueError as exc:
            raise SSRFBlockedError() from exc

        internal = allow_internal and host in self._allowed_hosts
        if not internal and port not in {80, 443}:
            raise SSRFBlockedError()

        addresses = await self._resolve(host, port)
        if not addresses:
            raise SSRFBlockedError()
        if not internal and any(not _is_public_ip(address) for address in addresses):
            raise SSRFBlockedError()

        return ValidatedURL(
            url=url,
            host=host,
            port=port,
            pinned_ip=addresses[0],
        )

    async def _resolve(self, host: str, port: int) -> list[str]:
        try:
            literal = ipaddress.ip_address(host.split("%", 1)[0])
        except ValueError:
            try:
                return await self._resolver(host, port)
            except OSError as exc:
                raise SSRFBlockedError() from exc
        return [str(literal)]

    @staticmethod
    async def _default_resolve(host: str, port: int) -> list[str]:
        infos = await asyncio.to_thread(
            socket.getaddrinfo,
            host,
            port,
            type=socket.SOCK_STREAM,
        )
        return sorted({str(info[4][0]).split("%", 1)[0] for info in infos})


class PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(
        self,
        backend: httpcore.AsyncNetworkBackend,
        pinned_ip: str,
    ) -> None:
        self._backend = backend
        self._pinned_ip = pinned_ip

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._backend.connect_tcp(
            self._pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._backend.connect_unix_socket(
            path,
            timeout=timeout,
            socket_options=socket_options,
        )

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    def __init__(self, pinned_ip: str) -> None:
        super().__init__(verify=True, trust_env=False, http1=True, http2=False)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=5.0,
            http1=True,
            http2=False,
            network_backend=PinnedNetworkBackend(
                httpcore.AnyIOBackend(),
                pinned_ip,
            ),
        )


class SafeHttpClient:
    def __init__(
        self,
        guard: SSRFGuard,
        *,
        timeout: httpx.Timeout | None = None,
        max_redirects: int = 5,
        transport_factory: Callable[[str], httpx.AsyncBaseTransport] | None = None,
    ) -> None:
        if max_redirects < 0:
            raise ValueError("max_redirects must be non-negative")
        self._guard = guard
        self._timeout = timeout or httpx.Timeout(10.0, connect=3.0)
        self._max_redirects = max_redirects
        self._transport_factory = transport_factory or PinnedAsyncHTTPTransport

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        content: bytes | None = None,
        allow_internal: bool = False,
    ) -> httpx.Response:
        current_url = url
        current_method = method
        current_content = content

        for _ in range(self._max_redirects + 1):
            validated = await self._guard.validate_url(
                current_url,
                allow_internal=allow_internal,
            )
            transport = self._transport_factory(validated.pinned_ip)
            async with httpx.AsyncClient(
                transport=transport,
                follow_redirects=False,
                timeout=self._timeout,
                trust_env=False,
            ) as client:
                response = await client.request(
                    current_method,
                    current_url,
                    headers=headers,
                    content=current_content,
                )

            if response.status_code not in _REDIRECT_STATUSES:
                return response

            location = response.headers.get("location")
            if not location:
                raise SSRFBlockedError()

            current_url = urljoin(str(response.url), location)
            if response.status_code in _SEE_OTHER_STATUSES and current_method != "HEAD":
                current_method = "GET"
                current_content = None

        raise SSRFBlockedError()


def _is_public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if not address.is_global:
        return False
    return not any(address in network for network in _BLOCKED_NETWORKS)
