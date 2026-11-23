from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from paysentineliq.application.errors import (
    AccountNotVerifiedError,
    AuthNotConfiguredError,
    EmailAlreadyExistsError,
    InvalidAuthTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    OAuthAuthenticationError,
    PasswordPolicyError,
    RefreshTokenReuseError,
    TooManyAttemptsError,
)
from paysentineliq.application.legal import LEGAL_DOCUMENTS, LEGAL_VERSION
from paysentineliq.application.notifications.auth_emails import (
    AuthEmail,
    AuthEmailKind,
    render_auth_email,
)
from paysentineliq.application.ports.auth_unit_of_work import AuthUnitOfWork
from paysentineliq.application.ports.oidc import GoogleIdentity
from paysentineliq.application.ports.password_hasher import PasswordHasher
from paysentineliq.application.ports.revoked_tokens import RevokedTokenStore
from paysentineliq.application.ports.token_service import (
    AccessTokenClaims,
    AccessTokenService,
)
from paysentineliq.application.security.account_lockout import lockout_delay_seconds
from paysentineliq.application.security.auth_tokens import (
    generate_auth_token,
    hash_auth_token,
)
from paysentineliq.application.security.password_policy import validate_password
from paysentineliq.application.security.refresh_tokens import (
    generate_refresh_token,
    hash_refresh_token,
)
from paysentineliq.domain.auth_token import AuthTokenType
from paysentineliq.domain.legal_consent import LegalConsent
from paysentineliq.domain.user import User

_MAX_IP_LENGTH = 64
_MAX_USER_AGENT_LENGTH = 512


@dataclass(frozen=True, slots=True)
class AuthRequestContext:
    ip: str | None = None
    user_agent: str | None = None
    locale: str | None = None


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: User
    access_token: str
    expires_in_seconds: int
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True, slots=True)
class _SessionDraft:
    auth_result: AuthResult
    family_id: UUID


class AuthService:
    def __init__(
        self,
        unit_of_work: AuthUnitOfWork,
        token_service: AccessTokenService,
        revoked_tokens: RevokedTokenStore,
        *,
        refresh_ttl_days: int,
        clock: Callable[[], datetime] | None = None,
        password_hasher: PasswordHasher | None = None,
        password_min_length: int = 10,
        password_max_length: int = 128,
        verification_ttl_minutes: int = 1440,
        reset_ttl_minutes: int = 30,
        public_base_url: str = "",
        legal_version: str = LEGAL_VERSION,
        lockout_max_attempts: int = 5,
        lockout_base_seconds: int = 30,
        lockout_max_seconds: int = 3600,
    ) -> None:
        if refresh_ttl_days <= 0:
            raise ValueError("refresh_ttl_days must be positive")
        self._unit_of_work = unit_of_work
        self._token_service = token_service
        self._revoked_tokens = revoked_tokens
        self._refresh_ttl = timedelta(days=refresh_ttl_days)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._password_hasher = password_hasher
        self._password_min_length = password_min_length
        self._password_max_length = password_max_length
        self._verification_ttl = timedelta(minutes=verification_ttl_minutes)
        self._reset_ttl = timedelta(minutes=reset_ttl_minutes)
        self._public_base_url = public_base_url.rstrip("/")
        self._legal_version = legal_version
        self._lockout_max_attempts = lockout_max_attempts
        self._lockout_base_seconds = lockout_base_seconds
        self._lockout_max_seconds = lockout_max_seconds

    async def login_with_google(
        self,
        identity: GoogleIdentity,
        context: AuthRequestContext | None = None,
    ) -> AuthResult:
        ctx = _sanitize_context(context)
        now = self._clock()

        async with self._unit_of_work as uow:
            user = await uow.users.get_by_google_sub(identity.google_sub)
            event_type = "login"

            if user is None:
                existing = await uow.users.get_by_email(identity.email)
                if existing is not None:
                    if existing.google_sub is not None:
                        await self._event(
                            uow,
                            "google_link_blocked",
                            existing.id,
                            ctx,
                            {"reason": "sub_conflict"},
                        )
                        await uow.commit()
                        raise OAuthAuthenticationError()
                    if existing.email_verified_at is None:
                        await self._event(
                            uow,
                            "google_link_blocked",
                            existing.id,
                            ctx,
                            {"reason": "email_unverified"},
                        )
                        await uow.commit()
                        raise OAuthAuthenticationError()
                    await uow.users.link_google_sub(
                        existing.id,
                        google_sub=identity.google_sub,
                    )
                    updated = await uow.users.update_profile(
                        existing.id,
                        email=normalize_email(identity.email),
                        name=identity.name,
                    )
                    if updated is None:
                        raise OAuthAuthenticationError()
                    user = updated
                    event_type = "google_linked"
                    await self._ensure_consents(uow, user, ctx, source="google_signin", now=now)
                else:
                    try:
                        user = await uow.users.create(
                            google_sub=identity.google_sub,
                            email=normalize_email(identity.email),
                            name=identity.name,
                        )
                    except EmailAlreadyExistsError as exc:
                        await uow.rollback()
                        raise OAuthAuthenticationError() from exc
                    await uow.users.mark_email_verified(user.id, verified_at=now)
                    user = replace(user, email_verified_at=now)
                    await self._ensure_consents(uow, user, ctx, source="google_signup", now=now)
                    event_type = "google_signup"
            else:
                updated = await uow.users.update_profile(
                    user.id,
                    email=normalize_email(identity.email),
                    name=identity.name,
                )
                if updated is None:
                    raise OAuthAuthenticationError()
                user = updated
                if user.email_verified_at is None:
                    await uow.users.mark_email_verified(user.id, verified_at=now)
                    user = replace(user, email_verified_at=now)
                await self._ensure_consents(uow, user, ctx, source="google_signin", now=now)

            result = self._issue_session(user, family_id=uuid4())
            await uow.refresh_tokens.add(
                user_id=user.id,
                token_hash=hash_refresh_token(result.auth_result.refresh_token),
                family_id=result.family_id,
                expires_at=result.auth_result.refresh_expires_at,
            )
            await self._event(uow, event_type, user.id, ctx, {"method": "google"})
            await uow.commit()

        return result.auth_result

    async def register(
        self,
        *,
        name: str,
        email: str,
        password: str,
        context: AuthRequestContext | None = None,
    ) -> AuthEmail | None:
        hasher, now = self._require_password_ready()
        ctx = _sanitize_context(context)
        normalized_email = normalize_email(email)
        violations = validate_password(
            password,
            email=normalized_email,
            name=name,
            min_length=self._password_min_length,
            max_length=self._password_max_length,
        )
        if violations:
            raise PasswordPolicyError(violations)

        password_hash = hasher.hash(password)
        token = generate_auth_token()

        async with self._unit_of_work as uow:
            existing = await uow.users.get_by_email(normalized_email)
            if existing is not None:
                await self._event(
                    uow,
                    "register_duplicate",
                    existing.id,
                    ctx,
                    {"method": "password"},
                )
                await uow.commit()
                return self._render_email(
                    kind="email_already_registered",
                    to=existing.email,
                    ctx=ctx,
                    link=f"{self._public_base_url}/login",
                )

            try:
                user = await uow.users.create_password_user(
                    email=normalized_email,
                    name=name.strip(),
                    password_hash=password_hash,
                )
            except EmailAlreadyExistsError:
                await uow.rollback()
                return self._render_email(
                    kind="email_already_registered",
                    to=normalized_email,
                    ctx=ctx,
                    link=f"{self._public_base_url}/login",
                )

            await self._add_consents(uow, user, ctx, source="signup", now=now)
            await uow.auth_tokens.invalidate_unused(
                user_id=user.id,
                token_type=AuthTokenType.EMAIL_VERIFICATION,
                used_at=now,
            )
            await uow.auth_tokens.add(
                user_id=user.id,
                token_type=AuthTokenType.EMAIL_VERIFICATION,
                token_hash=hash_auth_token(token),
                expires_at=now + self._verification_ttl,
                created_ip=ctx.ip,
                created_user_agent=ctx.user_agent,
            )
            await self._event(uow, "register", user.id, ctx, {"method": "password"})
            await uow.commit()

        return self._render_email(
            kind="verify_email",
            to=normalized_email,
            ctx=ctx,
            link=self._link("verificar-email", token),
        )

    async def login(
        self,
        *,
        email: str,
        password: str,
        context: AuthRequestContext | None = None,
    ) -> AuthResult:
        hasher, now = self._require_password_ready()
        ctx = _sanitize_context(context)
        normalized_email = normalize_email(email)

        async with self._unit_of_work as uow:
            user = await uow.users.get_by_email(normalized_email)

            if user is None or user.password_hash is None:
                hasher.verify_dummy(password)
                await self._event(
                    uow,
                    "login_failed",
                    user.id if user is not None else None,
                    ctx,
                    {"method": "password"},
                )
                await uow.commit()
                raise InvalidCredentialsError()

            password_matches = hasher.verify(user.password_hash, password)

            if user.locked_until is not None and user.locked_until > now:
                if not password_matches:
                    raise InvalidCredentialsError()
                retry_after = max(1, int((user.locked_until - now).total_seconds()))
                raise TooManyAttemptsError(retry_after)

            if not password_matches:
                failed = user.failed_login_count + 1
                delay = lockout_delay_seconds(
                    failed,
                    max_attempts=self._lockout_max_attempts,
                    base_seconds=self._lockout_base_seconds,
                    max_seconds=self._lockout_max_seconds,
                )
                locked_until = now + timedelta(seconds=delay) if delay else None
                await uow.users.record_login_failure(
                    user.id,
                    failed_login_count=failed,
                    locked_until=locked_until,
                )
                await self._event(
                    uow,
                    "login_failed",
                    user.id,
                    ctx,
                    {"method": "password"},
                )
                if locked_until is not None:
                    await self._event(
                        uow,
                        "account_locked",
                        user.id,
                        ctx,
                        {"lock_seconds": str(delay)},
                    )
                await uow.commit()
                raise InvalidCredentialsError()

            if user.email_verified_at is None:
                await uow.users.reset_login_failures(user.id)
                await self._event(uow, "login_unverified", user.id, ctx, {"method": "password"})
                await uow.commit()
                raise AccountNotVerifiedError()

            if hasher.needs_rehash(user.password_hash):
                rehashed = hasher.hash(password)
                await uow.users.set_password_hash(
                    user.id,
                    password_hash=rehashed,
                    changed_at=now,
                )
                user = replace(user, password_hash=rehashed)

            await uow.users.reset_login_failures(user.id)
            result = self._issue_session(user, family_id=uuid4())
            await uow.refresh_tokens.add(
                user_id=user.id,
                token_hash=hash_refresh_token(result.auth_result.refresh_token),
                family_id=result.family_id,
                expires_at=result.auth_result.refresh_expires_at,
            )
            await self._event(uow, "login", user.id, ctx, {"method": "password"})
            await uow.commit()

        return result.auth_result

    async def verify_email(
        self,
        *,
        token: str,
        context: AuthRequestContext | None = None,
    ) -> None:
        _, now = self._require_password_ready()
        ctx = _sanitize_context(context)

        async with self._unit_of_work as uow:
            record = await uow.auth_tokens.get_by_hash(hash_auth_token(token))
            if (
                record is None
                or record.token_type is not AuthTokenType.EMAIL_VERIFICATION
                or record.used_at is not None
                or record.expires_at <= now
            ):
                raise InvalidAuthTokenError()

            await uow.auth_tokens.mark_used(record.id, used_at=now)
            await uow.users.mark_email_verified(record.user_id, verified_at=now)
            await self._event(uow, "email_verified", record.user_id, ctx, {})
            await uow.commit()

    async def resend_verification(
        self,
        *,
        email: str,
        context: AuthRequestContext | None = None,
    ) -> AuthEmail | None:
        _, now = self._require_password_ready()
        ctx = _sanitize_context(context)
        normalized_email = normalize_email(email)
        token = generate_auth_token()

        async with self._unit_of_work as uow:
            user = await uow.users.get_by_email(normalized_email)
            if user is None or user.password_hash is None or user.email_verified_at is not None:
                await uow.commit()
                return None

            await uow.auth_tokens.invalidate_unused(
                user_id=user.id,
                token_type=AuthTokenType.EMAIL_VERIFICATION,
                used_at=now,
            )
            await uow.auth_tokens.add(
                user_id=user.id,
                token_type=AuthTokenType.EMAIL_VERIFICATION,
                token_hash=hash_auth_token(token),
                expires_at=now + self._verification_ttl,
                created_ip=ctx.ip,
                created_user_agent=ctx.user_agent,
            )
            await self._event(uow, "verification_resent", user.id, ctx, {})
            await uow.commit()

        return self._render_email(
            kind="verify_email",
            to=normalized_email,
            ctx=ctx,
            link=self._link("verificar-email", token),
        )

    async def forgot_password(
        self,
        *,
        email: str,
        context: AuthRequestContext | None = None,
    ) -> AuthEmail | None:
        _, now = self._require_password_ready()
        ctx = _sanitize_context(context)
        normalized_email = normalize_email(email)
        token = generate_auth_token()

        async with self._unit_of_work as uow:
            user = await uow.users.get_by_email(normalized_email)
            if user is None:
                await uow.commit()
                return None

            await self._event(uow, "password_reset_requested", user.id, ctx, {})

            if user.password_hash is None:
                await uow.commit()
                return self._render_email(
                    kind="google_account_reset",
                    to=user.email,
                    ctx=ctx,
                    link=f"{self._public_base_url}/login",
                )

            await uow.auth_tokens.invalidate_unused(
                user_id=user.id,
                token_type=AuthTokenType.PASSWORD_RESET,
                used_at=now,
            )
            await uow.auth_tokens.add(
                user_id=user.id,
                token_type=AuthTokenType.PASSWORD_RESET,
                token_hash=hash_auth_token(token),
                expires_at=now + self._reset_ttl,
                created_ip=ctx.ip,
                created_user_agent=ctx.user_agent,
            )
            await uow.commit()

        return self._render_email(
            kind="password_reset",
            to=normalized_email,
            ctx=ctx,
            link=self._link("redefinir-senha", token),
            token_minutes=int(self._reset_ttl.total_seconds() // 60),
        )

    async def reset_password(
        self,
        *,
        token: str,
        new_password: str,
        context: AuthRequestContext | None = None,
    ) -> AuthEmail | None:
        hasher, now = self._require_password_ready()
        ctx = _sanitize_context(context)

        async with self._unit_of_work as uow:
            record = await uow.auth_tokens.get_by_hash(hash_auth_token(token))
            if (
                record is None
                or record.token_type is not AuthTokenType.PASSWORD_RESET
                or record.used_at is not None
                or record.expires_at <= now
            ):
                raise InvalidAuthTokenError()

            user = await uow.users.get_by_id(record.user_id)
            if user is None or user.password_hash is None:
                raise InvalidAuthTokenError()

            violations = validate_password(
                new_password,
                email=user.email,
                name=user.name,
                min_length=self._password_min_length,
                max_length=self._password_max_length,
            )
            if violations:
                raise PasswordPolicyError(violations)

            await uow.users.set_password_hash(
                user.id,
                password_hash=hasher.hash(new_password),
                changed_at=now,
            )
            await uow.auth_tokens.mark_used(record.id, used_at=now)
            await uow.users.reset_login_failures(user.id)
            await uow.refresh_tokens.revoke_all_for_user(user.id, now)
            await self._event(uow, "password_reset_completed", user.id, ctx, {})
            await uow.commit()
            email = user.email

        return self._render_email(
            kind="password_changed",
            to=email,
            ctx=ctx,
            link=f"{self._public_base_url}/login",
        )

    async def change_password(
        self,
        *,
        user_id: UUID,
        current_password: str,
        new_password: str,
        context: AuthRequestContext | None = None,
    ) -> None:
        hasher, now = self._require_password_ready()
        ctx = _sanitize_context(context)

        async with self._unit_of_work as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None or user.password_hash is None:
                hasher.verify_dummy(current_password)
                raise InvalidCredentialsError()

            if not hasher.verify(user.password_hash, current_password):
                await self._event(uow, "password_change_failed", user.id, ctx, {})
                await uow.commit()
                raise InvalidCredentialsError()

            violations = validate_password(
                new_password,
                email=user.email,
                name=user.name,
                min_length=self._password_min_length,
                max_length=self._password_max_length,
            )
            if violations:
                raise PasswordPolicyError(violations)

            await uow.users.set_password_hash(
                user.id,
                password_hash=hasher.hash(new_password),
                changed_at=now,
            )
            await uow.users.reset_login_failures(user.id)
            await uow.refresh_tokens.revoke_all_for_user(user.id, now)
            await self._event(uow, "password_changed", user.id, ctx, {})
            await uow.commit()

    async def refresh(self, raw_refresh_token: str) -> AuthResult:
        token_hash = hash_refresh_token(raw_refresh_token)
        now = self._clock()

        async with self._unit_of_work as uow:
            record = await uow.refresh_tokens.get_for_update(token_hash)
            if record is None or record.expires_at <= now:
                raise InvalidRefreshTokenError()

            if record.revoked_at is not None:
                await uow.refresh_tokens.revoke_family(record.family_id, now)
                await uow.commit()
                raise RefreshTokenReuseError()

            user = await uow.users.get_by_id(record.user_id)
            if user is None:
                raise InvalidRefreshTokenError()

            await uow.refresh_tokens.revoke(record.id, now)
            session = self._issue_session(user, family_id=record.family_id)
            await uow.refresh_tokens.add(
                user_id=user.id,
                token_hash=hash_refresh_token(session.auth_result.refresh_token),
                family_id=session.family_id,
                expires_at=session.auth_result.refresh_expires_at,
            )
            await uow.commit()

        return session.auth_result

    async def logout(
        self,
        raw_refresh_token: str | None,
        access_claims: AccessTokenClaims | None,
        context: AuthRequestContext | None = None,
    ) -> None:
        now = self._clock()
        ctx = _sanitize_context(context)
        event_user_id: UUID | None = access_claims.sub if access_claims is not None else None

        if raw_refresh_token:
            async with self._unit_of_work as uow:
                record = await uow.refresh_tokens.get_for_update(
                    hash_refresh_token(raw_refresh_token)
                )
                if record is not None and record.revoked_at is None:
                    await uow.refresh_tokens.revoke_family(record.family_id, now)
                    event_user_id = record.user_id
                await self._event(uow, "logout", event_user_id, ctx, {})
                await uow.commit()
        elif event_user_id is not None:
            async with self._unit_of_work as uow:
                await self._event(uow, "logout", event_user_id, ctx, {})
                await uow.commit()

        if access_claims is not None:
            await self._revoked_tokens.revoke(
                access_claims.jti,
                access_claims.exp,
            )

    def _issue_session(self, user: User, *, family_id: UUID) -> _SessionDraft:
        issued = self._token_service.issue(user)
        return _SessionDraft(
            auth_result=AuthResult(
                user=user,
                access_token=issued.token,
                expires_in_seconds=issued.expires_in_seconds,
                refresh_token=generate_refresh_token(),
                refresh_expires_at=self._clock() + self._refresh_ttl,
            ),
            family_id=family_id,
        )

    def _require_password_ready(self) -> tuple[PasswordHasher, datetime]:
        if self._password_hasher is None or not self._public_base_url:
            raise AuthNotConfiguredError()
        return self._password_hasher, self._clock()

    def _link(self, path: str, token: str) -> str:
        return f"{self._public_base_url}/{path.lstrip('/')}?token={token}"

    async def _add_consents(
        self,
        uow: AuthUnitOfWork,
        user: User,
        ctx: AuthRequestContext,
        *,
        source: str,
        now: datetime,
    ) -> None:
        await uow.legal_consents.add_many(
            [
                LegalConsent(
                    user_id=user.id,
                    document=document,
                    version=self._legal_version,
                    accepted_at=now,
                    source=source,
                    created_ip=ctx.ip,
                    created_user_agent=ctx.user_agent,
                )
                for document in LEGAL_DOCUMENTS
            ],
        )

    async def _ensure_consents(
        self,
        uow: AuthUnitOfWork,
        user: User,
        ctx: AuthRequestContext,
        *,
        source: str,
        now: datetime,
    ) -> None:
        if await uow.legal_consents.has_version(user.id, self._legal_version):
            return
        await self._add_consents(uow, user, ctx, source=source, now=now)

    async def _event(
        self,
        uow: AuthUnitOfWork,
        event_type: str,
        user_id: UUID | None,
        ctx: AuthRequestContext,
        metadata: dict[str, str],
    ) -> None:
        from paysentineliq.domain.auth_event import AuthEvent

        await uow.auth_events.add(
            AuthEvent(
                event_type=event_type,
                user_id=user_id,
                created_ip=ctx.ip,
                created_user_agent=ctx.user_agent,
                metadata=metadata,
            ),
        )

    def _render_email(
        self,
        *,
        kind: AuthEmailKind,
        to: str,
        ctx: AuthRequestContext,
        link: str,
        token_minutes: int | None = None,
    ) -> AuthEmail:
        return render_auth_email(
            kind=kind,
            to=to,
            locale=ctx.locale,
            link=link,
            token_minutes=token_minutes,
        )


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _sanitize_context(context: AuthRequestContext | None) -> AuthRequestContext:
    if context is None:
        return AuthRequestContext()

    ip = context.ip.strip()[:_MAX_IP_LENGTH] if context.ip and context.ip.strip() else None
    user_agent = (
        context.user_agent.strip()[:_MAX_USER_AGENT_LENGTH]
        if context.user_agent and context.user_agent.strip()
        else None
    )
    locale = context.locale.strip()[:16] if context.locale and context.locale.strip() else None
    return AuthRequestContext(ip=ip, user_agent=user_agent, locale=locale)
