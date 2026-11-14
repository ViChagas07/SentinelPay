from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from paysentineliq.application.errors import (
    InvalidRefreshTokenError,
    OAuthAuthenticationError,
    RefreshTokenReuseError,
)
from paysentineliq.application.ports.auth_unit_of_work import AuthUnitOfWork
from paysentineliq.application.ports.oidc import GoogleIdentity
from paysentineliq.application.ports.revoked_tokens import RevokedTokenStore
from paysentineliq.application.ports.token_service import (
    AccessTokenClaims,
    AccessTokenService,
)
from paysentineliq.application.security.refresh_tokens import (
    generate_refresh_token,
    hash_refresh_token,
)
from paysentineliq.domain.user import User


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: User
    access_token: str
    expires_in_seconds: int
    refresh_token: str
    refresh_expires_at: datetime


class AuthService:
    def __init__(
        self,
        unit_of_work: AuthUnitOfWork,
        token_service: AccessTokenService,
        revoked_tokens: RevokedTokenStore,
        *,
        refresh_ttl_days: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if refresh_ttl_days <= 0:
            raise ValueError("refresh_ttl_days must be positive")
        self._unit_of_work = unit_of_work
        self._token_service = token_service
        self._revoked_tokens = revoked_tokens
        self._refresh_ttl = timedelta(days=refresh_ttl_days)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def login_with_google(self, identity: GoogleIdentity) -> AuthResult:
        async with self._unit_of_work as uow:
            user = await uow.users.get_by_google_sub(identity.google_sub)
            if user is None:
                user = await uow.users.create(
                    google_sub=identity.google_sub,
                    email=identity.email,
                    name=identity.name,
                )
            else:
                updated = await uow.users.update_profile(
                    user.id,
                    email=identity.email,
                    name=identity.name,
                )
                if updated is None:
                    raise OAuthAuthenticationError()
                user = updated

            result = self._issue_session(user, family_id=uuid4())
            await uow.refresh_tokens.add(
                user_id=user.id,
                token_hash=hash_refresh_token(result.auth_result.refresh_token),
                family_id=result.family_id,
                expires_at=result.auth_result.refresh_expires_at,
            )
            await uow.commit()

        return result.auth_result

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
    ) -> None:
        now = self._clock()

        if raw_refresh_token:
            async with self._unit_of_work as uow:
                record = await uow.refresh_tokens.get_for_update(
                    hash_refresh_token(raw_refresh_token)
                )
                if record is not None and record.revoked_at is None:
                    await uow.refresh_tokens.revoke_family(
                        record.family_id,
                        now,
                    )
                await uow.commit()

        if access_claims is not None:
            await self._revoked_tokens.revoke(
                access_claims.jti,
                access_claims.exp,
            )

    def _issue_session(self, user: User, *, family_id: UUID) -> "_SessionDraft":
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


@dataclass(frozen=True, slots=True)
class _SessionDraft:
    auth_result: AuthResult
    family_id: UUID
