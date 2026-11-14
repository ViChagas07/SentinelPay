from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from paysentineliq.interface.api.problems import build_problem_response


class UploadSizeLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        path: str,
        max_bytes: int,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.app = app
        self._path = path
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or str(scope.get("path", "")) != self._path:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        declared_length = _parse_length(headers.get("content-length"))
        if declared_length is not None and declared_length > self._max_bytes:
            await self._reject(scope, receive, send)
            return

        received = 0
        too_large = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    too_large = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if too_large:
                if not response_started:
                    response_started = True
                    await self._reject(scope, receive, send)
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not too_large:
                raise
            if not response_started:
                response_started = True
                await self._reject(scope, receive, send)
            return
        if too_large and not response_started:
            await self._reject(scope, receive, send)

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        request = Request(scope)
        response = build_problem_response(
            request,
            status_code=413,
            code="upload_too_large",
            title="Payload too large",
            detail="Upload exceeds the allowed size.",
        )
        await response(scope, receive, send)


def _parse_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
