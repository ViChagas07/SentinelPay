import asyncio

from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from paysentineliq.interface.api.problems import build_problem_response


class RequestBodyTooLargeError(Exception):
    pass


class MaxBodySizeMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = 0
            if declared_length > self._max_bytes:
                await self._reject(scope, receive, send)
                return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise RequestBodyTooLargeError
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestBodyTooLargeError:
            if response_started:
                raise
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope)
        response = build_problem_response(
            request,
            status_code=413,
            code="request_too_large",
            title="Payload too large",
            detail="Request body is too large.",
        )
        await response(scope, receive, send)


class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, timeout_seconds: float) -> None:
        super().__init__(app)
        self._timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            return build_problem_response(
                request,
                status_code=504,
                code="request_timeout",
                title="Gateway timeout",
                detail="The request took too long.",
            )
