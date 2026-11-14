from starlette.responses import Response

from paysentineliq.interface.api.csrf import clear_csrf_cookie

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
OIDC_STATE_COOKIE_NAME = "oidc_state"
OIDC_STATE_COOKIE_PATH = "/api/v1/auth/google"


def set_refresh_cookie(
    response: Response,
    token: str,
    *,
    max_age_seconds: int,
    secure: bool,
    domain: str | None,
) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        domain=domain or None,
    )


def clear_refresh_cookie(
    response: Response,
    *,
    domain: str | None,
) -> None:
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        domain=domain or None,
    )


def set_oidc_state_cookie(
    response: Response,
    state: str,
    *,
    max_age_seconds: int,
    secure: bool,
    domain: str | None,
) -> None:
    response.set_cookie(
        key=OIDC_STATE_COOKIE_NAME,
        value=state,
        max_age=max_age_seconds,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=OIDC_STATE_COOKIE_PATH,
        domain=domain or None,
    )


def clear_oidc_state_cookie(
    response: Response,
    *,
    domain: str | None,
) -> None:
    response.delete_cookie(
        OIDC_STATE_COOKIE_NAME,
        path=OIDC_STATE_COOKIE_PATH,
        domain=domain or None,
    )


def clear_auth_cookies(
    response: Response,
    *,
    domain: str | None,
) -> None:
    clear_refresh_cookie(response, domain=domain)
    clear_csrf_cookie(response, domain=domain)
