import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from paysentineliq.domain.errors import DomainError
from paysentineliq.interface.api.constants import REQUEST_ID_HEADER

_logger = logging.getLogger("paysentineliq")
_PROBLEM_BASE = "https://paysentineliq.local/problems"

_HTTP_PROBLEMS: dict[int, tuple[str, str]] = {
    400: ("bad_request", "Bad request"),
    401: ("unauthorized", "Unauthorized"),
    403: ("forbidden", "Forbidden"),
    404: ("not_found", "Not found"),
    405: ("method_not_allowed", "Method not allowed"),
    409: ("conflict", "Conflict"),
    422: ("unprocessable_entity", "Unprocessable entity"),
    429: ("rate_limited", "Too many requests"),
}


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", "")
    return value if isinstance(value, str) else ""


def _instance(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return request.url.path


def build_problem_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    extra_headers: Mapping[str, str] | None = None,
    extra_fields: Mapping[str, object] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    content: dict[str, object] = {
        "type": f"{_PROBLEM_BASE}/{code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": _instance(request),
        "code": code,
        "request_id": request_id,
    }
    if extra_fields:
        content.update(extra_fields)
    headers: dict[str, str] = {}
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
        headers=headers or None,
    )


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        return await unexpected_exception_handler(request, exc)

    _logger.warning("domain_error code=%s", exc.code)
    retry_after = getattr(exc, "retry_after_seconds", None)
    extra_headers: dict[str, str] | None = None
    if isinstance(retry_after, int) and retry_after > 0:
        extra_headers = {"Retry-After": str(retry_after)}

    raw_evidence = getattr(exc, "evidence", None)
    extra_fields: dict[str, object] | None = None
    if isinstance(raw_evidence, (tuple, list)) and all(
        isinstance(item, str) for item in raw_evidence
    ):
        extra_fields = {"evidence": list(raw_evidence)}
    raw_extra_fields = getattr(exc, "extra_fields", None)
    if isinstance(raw_extra_fields, dict):
        extra_fields = {**(extra_fields or {}), **raw_extra_fields}

    return build_problem_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        title=exc.title,
        detail=exc.message,
        extra_headers=extra_headers,
        extra_fields=extra_fields,
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return await unexpected_exception_handler(request, exc)

    _logger.warning("validation_error")
    return build_problem_response(
        request,
        status_code=422,
        code="validation_error",
        title="Validation error",
        detail="Request validation failed.",
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return await unexpected_exception_handler(request, exc)

    code, title = _HTTP_PROBLEMS.get(exc.status_code, ("http_error", "HTTP error"))
    return build_problem_response(
        request,
        status_code=exc.status_code,
        code=code,
        title=title,
        detail=title,
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _logger.error("unhandled_exception error_type=%s", type(exc).__name__)
    return build_problem_response(
        request,
        status_code=500,
        code="internal_error",
        title="Internal server error",
        detail="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
