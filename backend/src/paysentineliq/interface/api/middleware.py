import logging
import re
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from paysentineliq.infrastructure.logging import reset_request_id, set_request_id
from paysentineliq.interface.api.constants import REQUEST_ID_HEADER

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_logger = logging.getLogger("paysentineliq")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        if incoming is not None and _SAFE_REQUEST_ID.fullmatch(incoming):
            request_id = incoming
        else:
            request_id = str(uuid4())

        request.state.request_id = request_id
        token = set_request_id(request_id)
        started = time.perf_counter()
        metrics = getattr(request.app.state, "metrics", None)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            elapsed = time.perf_counter() - started
            if metrics is not None:
                route = request.scope.get("route")
                metrics.record_http_request(
                    request.method,
                    getattr(route, "path", "unmatched"),
                    response.status_code,
                    elapsed,
                )
            _logger.info(
                "request_completed method=%s path=%s status=%d duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                elapsed * 1000,
            )
            return response
        except Exception:
            if metrics is not None:
                route = request.scope.get("route")
                metrics.record_http_request(
                    request.method,
                    getattr(route, "path", "unmatched"),
                    500,
                    time.perf_counter() - started,
                )
            raise
        finally:
            reset_request_id(token)
