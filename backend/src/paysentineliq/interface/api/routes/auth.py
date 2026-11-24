import hmac
import logging
import re
import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from paysentineliq.application.commands.auth import (
    AuthRequestContext,
    AuthService,
    normalize_email,
)
from paysentineliq.application.errors import (
    AuthNotConfiguredError,
    EmailNotVerifiedError,
    InvalidOAuthStateError,
    InvalidRefreshTokenError,
    OAuthAuthenticationError,
    RefreshTokenReuseError,
    TooManyAttemptsError,
)
from paysentineliq.application.notifications.auth_delivery import deliver_auth_email
from paysentineliq.application.notifications.auth_emails import AuthEmail
from paysentineliq.application.ports.messaging import EmailPort
from paysentineliq.application.ports.oidc import OIDCClient
from paysentineliq.application.ports.oidc_state import OIDCState, OIDCStateStore
from paysentineliq.application.ports.token_service import AccessTokenClaims
from paysentineliq.application.security.password_policy import password_policy_payload
from paysentineliq.application.security.refresh_tokens import hash_refresh_token
from paysentineliq.domain.user import User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.security.auth_rate_limit import (
    AuthRateLimiter,
    AuthRateLimitScope,
)
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
    get_auth_email_sender,
    get_auth_rate_limiter,
    get_auth_request_context,
    get_auth_service,
    get_brute_force,
    get_current_user,
    get_oidc_client,
    get_oidc_state_store,
    get_optional_access_claims,
    require_password_auth,
    require_password_email,
)
from paysentineliq.interface.api.problems import build_problem_response

router = APIRouter(prefix="/auth", tags=["auth"])
_logger = logging.getLogger("paysentineliq")

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _validate_email(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) > 320 or not _EMAIL_RE.fullmatch(normalized):
        raise ValueError("invalid e-mail")
    return normalized


class RegisterRequest(_StrictModel):
    nome_completo: str = Field(min_length=1, max_length=255)
    email: str = Field(max_length=320)
    senha: str = Field(min_length=1, max_length=256)
    aceite_termos: Literal[True]
    aceite_privacidade: Literal[True]

    @field_validator("nome_completo")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _validate_email(value)


class LoginRequest(_StrictModel):
    email: str = Field(max_length=320)
    senha: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _validate_email(value)


class EmailRequest(_StrictModel):
    email: str = Field(max_length=320)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return _validate_email(value)


class TokenRequest(_StrictModel):
    token: str = Field(min_length=10, max_length=512)


class ResetPasswordRequest(_StrictModel):
    token: str = Field(min_length=10, max_length=512)
    nova_senha: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(_StrictModel):
    senha_atual: str = Field(min_length=1, max_length=256)
    nova_senha: str = Field(min_length=1, max_length=256)


async def _enforce_auth_rate_limit(
    limiter: AuthRateLimiter,
    scope: AuthRateLimitScope,
    request: Request,
    *,
    identifier: str,
) -> None:
    result = await limiter.consume(
        scope,
        ip=_client_ip(request),
        identifier=normalize_email(identifier),
    )
    if not result.allowed:
        raise TooManyAttemptsError(max(1, result.retry_after_seconds))


def _schedule_email(
    background_tasks: BackgroundTasks,
    sender: EmailPort,
    email: AuthEmail | None,
    settings: Settings,
) -> None:
    if email is None:
        return
    background_tasks.add_task(
        deliver_auth_email,
        sender,
        email,
        max_attempts=settings.auth_email_max_attempts,
    )


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
    auth_context: Annotated[AuthRequestContext, Depends(get_auth_request_context)],
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

    result = await auth_service.login_with_google(identity, auth_context)
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
    auth_context: Annotated[AuthRequestContext, Depends(get_auth_request_context)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> Response:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    await auth_service.logout(raw_token, claims, auth_context)
    response = Response(status_code=204)
    clear_auth_cookies(response, domain=settings.cookie_domain)
    return response


@router.get("/password-policy")
async def password_policy(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> JSONResponse:
    return JSONResponse(
        password_policy_payload(
            min_length=settings.password_min_length,
            max_length=settings.password_max_length,
            hibp_enabled=settings.password_hibp_enabled,
        )
    )


@router.get("/capabilities")
async def auth_capabilities(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> JSONResponse:
    return JSONResponse(
        {
            "password_enabled": settings.password_login_enabled,
            "signup_enabled": settings.password_signup_enabled,
            "password_reset_enabled": settings.password_reset_enabled,
            "google_enabled": settings.google_configured,
        }
    )


@router.post("/register", status_code=202, dependencies=[Depends(require_password_email)])
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    sender: Annotated[EmailPort, Depends(get_auth_email_sender)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
    auth_context: Annotated[AuthRequestContext, Depends(get_auth_request_context)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    request: Request,
) -> JSONResponse:
    await _enforce_auth_rate_limit(
        limiter,
        "register",
        request,
        identifier=payload.email,
    )
    email = await auth_service.register(
        name=payload.nome_completo,
        email=payload.email,
        password=payload.senha,
        context=auth_context,
    )
    _schedule_email(background_tasks, sender, email, settings)
    return JSONResponse({"status": "accepted"}, status_code=202)


@router.post("/login", dependencies=[Depends(require_password_auth)])
async def password_login(
    payload: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
    auth_context: Annotated[AuthRequestContext, Depends(get_auth_request_context)],
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Response:
    await _enforce_auth_rate_limit(limiter, "login", request, identifier=payload.email)
    result = await auth_service.login(
        email=payload.email,
        password=payload.senha,
        context=auth_context,
    )

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


@router.post(
    "/verify-email",
    status_code=204,
    dependencies=[Depends(require_password_auth)],
)
async def verify_email(
    payload: TokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    auth_context: Annotated[AuthRequestContext, Depends(get_auth_request_context)],
) -> Response:
    await auth_service.verify_email(token=payload.token, context=auth_context)
    return Response(status_code=204)


@router.post(
    "/resend-verification",
    status_code=202,
    dependencies=[Depends(require_password_email)],
)
async def resend_verification(
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    sender: Annotated[EmailPort, Depends(get_auth_email_sender)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
    auth_context: Annotated[AuthRequestContext, Depends(get_auth_request_context)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    request: Request,
) -> JSONResponse:
    await _enforce_auth_rate_limit(
        limiter,
        "resend",
        request,
        identifier=payload.email,
    )
    email = await auth_service.resend_verification(
        email=payload.email,
        context=auth_context,
    )
    _schedule_email(background_tasks, sender, email, settings)
    return JSONResponse({"status": "accepted"}, status_code=202)


@router.post(
    "/forgot-password",
    status_code=202,
    dependencies=[Depends(require_password_email)],
)
async def forgot_password(
    payload: EmailRequest,
    background_tasks: BackgroundTasks,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    sender: Annotated[EmailPort, Depends(get_auth_email_sender)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
    auth_context: Annotated[AuthRequestContext, Depends(get_auth_request_context)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    request: Request,
) -> JSONResponse:
    await _enforce_auth_rate_limit(limiter, "forgot", request, identifier=payload.email)
    email = await auth_service.forgot_password(
        email=payload.email,
        context=auth_context,
    )
    _schedule_email(background_tasks, sender, email, settings)
    return JSONResponse({"status": "accepted"}, status_code=202)


@router.post(
    "/reset-password",
    status_code=204,
    dependencies=[Depends(require_password_email)],
)
async def reset_password(
    payload: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    sender: Annotated[EmailPort, Depends(get_auth_email_sender)],
    auth_context: Annotated[AuthRequestContext, Depends(get_auth_request_context)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Response:
    email = await auth_service.reset_password(
        token=payload.token,
        new_password=payload.nova_senha,
        context=auth_context,
    )
    _schedule_email(background_tasks, sender, email, settings)
    return Response(status_code=204)


@router.post(
    "/change-password",
    status_code=204,
    dependencies=[Depends(require_password_auth)],
)
async def change_password(
    payload: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    auth_context: Annotated[AuthRequestContext, Depends(get_auth_request_context)],
) -> Response:
    await auth_service.change_password(
        user_id=user.id,
        current_password=payload.senha_atual,
        new_password=payload.nova_senha,
        context=auth_context,
    )
    return Response(status_code=204)


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
