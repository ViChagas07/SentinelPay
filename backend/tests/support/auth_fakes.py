"""In-memory auth fakes for unit tests. No real credentials or tokens."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

from paysentineliq.application.security.auth_tokens import hash_auth_token
from paysentineliq.domain.auth_event import AuthEvent
from paysentineliq.domain.auth_token import AuthToken, AuthTokenType
from paysentineliq.domain.legal_consent import LegalConsent
from paysentineliq.domain.refresh_token import RefreshTokenRecord
from paysentineliq.domain.user import Role, User


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: float) -> None:
        self.value = self.value + timedelta(**kwargs)


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.google_sub == google_sub),
            None,
        )

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        return next(
            (user for user in self.users.values() if user.email.strip().lower() == normalized),
            None,
        )

    async def create(
        self,
        *,
        google_sub: str,
        email: str,
        name: str | None,
        email_verified: bool = True,
    ) -> User:
        user = User(
            id=uuid4(),
            google_sub=google_sub,
            email=email,
            name=name,
            preferred_locale="pt-BR",
            timezone="America/Sao_Paulo",
            role=Role.USER,
            email_verified_at=datetime(2026, 1, 1, tzinfo=UTC) if email_verified else None,
        )
        self.users[user.id] = user
        return user

    async def create_password_user(
        self,
        *,
        email: str,
        name: str,
        password_hash: str,
    ) -> User:
        user = User(
            id=uuid4(),
            google_sub=None,
            email=email,
            name=name,
            preferred_locale="pt-BR",
            timezone="America/Sao_Paulo",
            role=Role.USER,
            password_hash=password_hash,
            email_verified_at=None,
        )
        self.users[user.id] = user
        return user

    async def update_profile(
        self,
        user_id: UUID,
        *,
        email: str,
        name: str | None,
    ) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        updated = replace(user, email=email, name=name)
        self.users[user_id] = updated
        return updated

    async def set_password_hash(
        self,
        user_id: UUID,
        *,
        password_hash: str,
        changed_at: datetime,
    ) -> None:
        user = self.users.get(user_id)
        if user is None:
            return
        self.users[user_id] = replace(
            user,
            password_hash=password_hash,
            password_changed_at=changed_at,
        )

    async def mark_email_verified(self, user_id: UUID, *, verified_at: datetime) -> None:
        user = self.users.get(user_id)
        if user is None:
            return
        self.users[user_id] = replace(user, email_verified_at=verified_at)

    async def record_login_failure(
        self,
        user_id: UUID,
        *,
        failed_login_count: int,
        locked_until: datetime | None,
    ) -> None:
        user = self.users.get(user_id)
        if user is None:
            return
        self.users[user_id] = replace(
            user,
            failed_login_count=failed_login_count,
            locked_until=locked_until,
        )

    async def reset_login_failures(self, user_id: UUID) -> None:
        user = self.users.get(user_id)
        if user is None:
            return
        self.users[user_id] = replace(user, failed_login_count=0, locked_until=None)

    async def link_google_sub(self, user_id: UUID, *, google_sub: str) -> None:
        user = self.users.get(user_id)
        if user is None:
            return
        self.users[user_id] = replace(user, google_sub=google_sub)


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.records: dict[str, RefreshTokenRecord] = {}

    async def add(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        family_id: UUID,
        expires_at: datetime,
    ) -> None:
        self.records[token_hash] = RefreshTokenRecord(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
            revoked_at=None,
        )

    async def get_for_update(self, token_hash: str) -> RefreshTokenRecord | None:
        return self.records.get(token_hash)

    async def revoke(self, token_id: UUID, revoked_at: datetime) -> None:
        for token_hash, record in list(self.records.items()):
            if record.id == token_id:
                self.records[token_hash] = replace(record, revoked_at=revoked_at)

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None:
        for token_hash, record in list(self.records.items()):
            if record.family_id == family_id and record.revoked_at is None:
                self.records[token_hash] = replace(record, revoked_at=revoked_at)

    async def revoke_all_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        for token_hash, record in list(self.records.items()):
            if record.user_id == user_id and record.revoked_at is None:
                self.records[token_hash] = replace(record, revoked_at=revoked_at)


class FakeAuthTokenRepository:
    def __init__(self) -> None:
        self.records: dict[str, AuthToken] = {}

    async def add(
        self,
        *,
        user_id: UUID,
        token_type: AuthTokenType,
        token_hash: str,
        expires_at: datetime,
        created_ip: str | None,
        created_user_agent: str | None,
    ) -> AuthToken:
        record = AuthToken(
            id=uuid4(),
            user_id=user_id,
            token_type=token_type,
            token_hash=token_hash,
            expires_at=expires_at,
            used_at=None,
            created_ip=created_ip,
            created_user_agent=created_user_agent,
        )
        self.records[token_hash] = record
        return record

    async def get_by_hash(self, token_hash: str) -> AuthToken | None:
        return self.records.get(token_hash)

    async def mark_used(self, token_id: UUID, *, used_at: datetime) -> None:
        for token_hash, record in list(self.records.items()):
            if record.id == token_id:
                self.records[token_hash] = replace(record, used_at=used_at)

    async def invalidate_unused(
        self,
        *,
        user_id: UUID,
        token_type: AuthTokenType,
        used_at: datetime,
    ) -> None:
        for token_hash, record in list(self.records.items()):
            if (
                record.user_id == user_id
                and record.token_type is token_type
                and record.used_at is None
            ):
                self.records[token_hash] = replace(record, used_at=used_at)

    def latest(self, token_type: AuthTokenType) -> AuthToken | None:
        candidates = [record for record in self.records.values() if record.token_type is token_type]
        return candidates[-1] if candidates else None


class FakeLegalConsentRepository:
    def __init__(self) -> None:
        self.entries: list[LegalConsent] = []

    async def add_many(self, consents: Sequence[LegalConsent]) -> None:
        self.entries.extend(consents)

    async def has_version(self, user_id: UUID, version: str) -> bool:
        return any(entry.user_id == user_id and entry.version == version for entry in self.entries)


class FakeAuthEventRepository:
    def __init__(self) -> None:
        self.events: list[AuthEvent] = []

    async def add(self, event: AuthEvent) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [event.event_type for event in self.events]


class FakeRevokedTokenStore:
    def __init__(self) -> None:
        self.revoked: dict[str, int] = {}

    async def revoke(self, jti: str, expires_at: int) -> None:
        self.revoked[jti] = expires_at

    async def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.users = FakeUserRepository()
        self.refresh_tokens = FakeRefreshTokenRepository()
        self.auth_tokens = FakeAuthTokenRepository()
        self.legal_consents = FakeLegalConsentRepository()
        self.auth_events = FakeAuthEventRepository()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def token_from_record(record: AuthToken) -> str | None:
    return next(
        (raw for raw, value in _RAW_TOKENS.items() if value == record.token_hash),
        None,
    )


_RAW_TOKENS: dict[str, str] = {}


def remember_token(raw: str) -> str:
    _RAW_TOKENS[raw] = hash_auth_token(raw)
    return raw
