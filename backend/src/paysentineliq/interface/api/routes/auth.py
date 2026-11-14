import hmac
import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from paysentineliq.application.errors import (
    AuthNotConfiguredError,
    EmailNotVerifiedError,
    InvalidOAuthStateError,
    InvalidRefreshTokenError,
    OAuthAuthenticationError,
    RefreshTokenReuseError,
    TooManyAttemptsError,
)
from paysentineliq.application.ports.oidc import OIDCClient
from paysentineliq.application.ports.oidc_state import OIDCState, OIDCStateStore
from paysentineliq.application.ports.token_service import AccessTokenClaims
from paysentineliq.application.security.refresh_tokens import hash_refresh_token
from paysentineliq.application.use_cases.auth import AuthService
from paysentineliq.domain.user import User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.security.bruteforce import BruteForceService
from paysentineliq.interface.api.auth_cookies import (
    OIDC_STATE_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    clear_auth_cookies,
    clear_oidc_state_cookie,
    set_oidc_state_cookie,
    set_refresh_cookie,
)
from paysentineliq.interface.api.csrf import (
    generate_csrf_token,
    require_csrf,
    set_csrf_cookie,
)
from paysentineliq.interface.api.dependencies import (
    get_app_settings,
    get_auth_service,
    get_brute_force,
    get_oidc_client,
    get_oidc_state_store,
    get_optional_access_claims,
)
from paysentineliq.interface.api.problems import build_problem_response

router = APIRouter(prefix="/auth", tags=["auth"])
_logger = logging.getLogger("paysentineliq")


@router.get("/google/login")
async def google_login(
    settings: Annotated[Settings, Depends(get_app_settings)],
    oidc: Annotated[OIDCClient, Depends(get_oidc_client)],
    state_store: Annotated[OIDCStateStore, Depends(get_oidc_state_store)],
) -> RedirectResponse:
    if not settings.google_configured or not settings.frontend_url:
        raise AuthNotConfiguredError()

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    await state_store.save(
        state,
        OIDCState(
            nonce=nonce,
            code_verifier=code_verifier,
            redirect_uri=settings.google_redirect_uri,
        ),
        ttl_seconds=settings.oidc_state_ttl_seconds,
    )
    url = await oidc.authorization_url(
        state=state,
        nonce=nonce,
        code_verifier=code_verifier,
    )
    response = RedirectResponse(url, status_code=302)
    set_oidc_state_cookie(
        response,
        state,
        max_age_seconds=settings.oidc_state_ttl_seconds,
        secure=_secure(settings),
        domain=settings.cookie_domain,
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    oidc: Annotated[OIDCClient, Depends(get_oidc_client)],
    state_store: Annotated[OIDCStateStore, Depends(get_oidc_state_store)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    brute_force: Annotated[BruteForceService, Depends(get_brute_force)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    state_cookie = request.cookies.get(OIDC_STATE_COOKIE_NAME)
    identifier = f"state:{state}" if state else "state:missing"

    if not state or not state_cookie or not hmac.compare_digest(state, state_cookie):
        await _record_failure(request, brute_force, identifier)
        raise InvalidOAuthStateError()

    await _ensure_not_blocked(request, brute_force, identifier)

    stored = await state_store.pop(state)
    if stored is None:
        await _record_failure(request, brute_force, identifier)
        raise InvalidOAuthStateError()

    if error or not code:
        await _record_failure(request, brute_force, identifier)
        raise OAuthAuthenticationError()

    try:
        identity = await oidc.exchange_code(
            code=code,
            code_verifier=stored.code_verifier,
            redirect_uri=stored.redirect_uri,
            expected_nonce=stored.nonce,
        )
    except (OAuthAuthenticationError, EmailNotVerifiedError):
        await _record_failure(request, brute_force, identifier)
        raise

    result = await auth_service.login_with_google(identity)
    await brute_force.reset(identifier=identifier, ip=_client_ip(request))

    response = RedirectResponse(settings.frontend_url, status_code=303)
    set_refresh_cookie(
        response,
        result.refresh_token,
        max_age_seconds=settings.refresh_token_ttl_days * 86400,
        secure=_secure(settings),
        domain=settings.cookie_domain,
    )
    set_csrf_cookie(
        response,
        generate_csrf_token(),
        secure=_secure(settings),
        domain=settings.cookie_domain,
    )
    clear_oidc_state_cookie(response, domain=settings.cookie_domain)
    return response


@router.post("/refresh")
async def refresh(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    brute_force: Annotated[BruteForceService, Depends(get_brute_force)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        return _problem_with_cleared_cookies(
            request,
            InvalidRefreshTokenError(),
            settings,
        )

    identifier = f"refresh:{hash_refresh_token(raw_token)[:16]}"
    await _ensure_not_blocked(request, brute_force, identifier)

    try:
        result = await auth_service.refresh(raw_token)
    except (InvalidRefreshTokenError, RefreshTokenReuseError) as exc:
        await _record_failure(request, brute_force, identifier)
        _logger.warning("refresh_failed code=%s", exc.code)
        return _problem_with_cleared_cookies(request, exc, settings)

    await brute_force.reset(identifier=identifier, ip=_client_ip(request))

    response = JSONResponse(
        {
            "access_token": result.access_token,
            "token_type": "bearer",  # nosec B105
            "expires_in": result.expires_in_seconds,
            "user": _user_payload(result.user),
        }
    )
    set_refresh_cookie(
        response,
        result.refresh_token,
        max_age_seconds=settings.refresh_token_ttl_days * 86400,
        secure=_secure(settings),
        domain=settings.cookie_domain,
    )
    set_csrf_cookie(
        response,
        generate_csrf_token(),
        secure=_secure(settings),
        domain=settings.cookie_domain,
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    claims: Annotated[
        AccessTokenClaims | None,
        Depends(get_optional_access_claims),
    ],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    await auth_service.logout(raw_token, claims)
    response = Response(status_code=204)
    clear_auth_cookies(response, domain=settings.cookie_domain)
    return response


def _secure(settings: Settings) -> bool:
    return settings.app_env != "local"


def _client_ip(request: Request) -> str:
    client = request.client
    return client.host if client is not None else "unknown"


async def _ensure_not_blocked(
    request: Request,
    brute_force: BruteForceService,
    identifier: str,
) -> None:
    status = await brute_force.check(
        identifier=identifier,
        ip=_client_ip(request),
    )
    if status.blocked:
        raise TooManyAttemptsError(max(1, status.retry_after_seconds))


async def _record_failure(
    request: Request,
    brute_force: BruteForceService,
    identifier: str,
) -> None:
    await brute_force.record_failure(
        identifier=identifier,
        ip=_client_ip(request),
    )


def _problem_with_cleared_cookies(
    request: Request,
    error: InvalidRefreshTokenError | RefreshTokenReuseError,
    settings: Settings,
) -> Response:
    response = build_problem_response(
        request,
        status_code=error.status_code,
        code=error.code,
        title=error.title,
        detail=error.message,
    )
    clear_auth_cookies(response, domain=settings.cookie_domain)
    return response


def _user_payload(user: User) -> dict[str, str | None]:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "preferred_locale": user.preferred_locale,
        "timezone": user.timezone,
    }
