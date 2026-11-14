from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from paysentineliq.domain.user import Role, User


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    sub: UUID
    role: Role
    jti: str
    exp: int
    iat: int


@dataclass(frozen=True, slots=True)
class IssuedAccessToken:
    token: str
    claims: AccessTokenClaims
    expires_in_seconds: int


class AccessTokenService(Protocol):
    def issue(self, user: User) -> IssuedAccessToken: ...

    def decode(self, token: str) -> AccessTokenClaims: ...
