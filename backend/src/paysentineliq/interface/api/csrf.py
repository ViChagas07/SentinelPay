import hmac
import secrets

from fastapi import Request
from starlette.responses import Response

from paysentineliq.application.errors import CsrfError

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(
    response: Response,
    token: str,
    *,
    secure: bool,
    domain: str | None = None,
) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        domain=domain or None,
    )


def clear_csrf_cookie(response: Response, *, domain: str | None = None) -> None:
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        domain=domain or None,
    )


def validate_csrf_token(cookie: str | None, header: str | None) -> None:
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise CsrfError()


def require_csrf(request: Request) -> None:
    validate_csrf_token(
        request.cookies.get(CSRF_COOKIE_NAME),
        request.headers.get(CSRF_HEADER_NAME),
    )
