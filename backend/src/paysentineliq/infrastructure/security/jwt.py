from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry

from paysentineliq.application.errors import InvalidAccessTokenError
from paysentineliq.application.ports.token_service import (
    AccessTokenClaims,
    IssuedAccessToken,
)
from paysentineliq.domain.user import Role, User

_ALGORITHM = "HS256"


class JwtAccessTokenService:
    def __init__(
        self,
        *,
        secret: str,
        ttl_minutes: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not secret:
            raise ValueError("secret must not be empty")
        if ttl_minutes <= 0:
            raise ValueError("ttl_minutes must be positive")
        self._key = OctKey.import_key(secret)
        self._ttl_seconds = ttl_minutes * 60
        self._clock = clock or (lambda: datetime.now(UTC))

    def issue(self, user: User) -> IssuedAccessToken:
        now = int(self._clock().timestamp())
        exp = now + self._ttl_seconds
        claims = AccessTokenClaims(
            sub=user.id,
            role=user.role,
            jti=str(uuid4()),
            exp=exp,
            iat=now,
        )
        token = jwt.encode(
            {"alg": _ALGORITHM},
            {
                "sub": str(claims.sub),
                "role": claims.role.value,
                "jti": claims.jti,
                "exp": claims.exp,
                "iat": claims.iat,
            },
            self._key,
        )
        return IssuedAccessToken(
            token=token,
            claims=claims,
            expires_in_seconds=self._ttl_seconds,
        )

    def decode(self, token: str) -> AccessTokenClaims:
        try:
            parsed = jwt.decode(
                token,
                self._key,
                algorithms=[_ALGORITHM],
            )
            registry = JWTClaimsRegistry(
                now=int(self._clock().timestamp()),
                exp={"essential": True},
                iat={"essential": True},
                sub={"essential": True},
                role={"essential": True},
                jti={"essential": True},
            )
            registry.validate(parsed.claims)

            sub = UUID(str(parsed.claims["sub"]))
            role = Role(str(parsed.claims["role"]))
            jti = str(parsed.claims["jti"])
            if not jti:
                raise ValueError("empty jti")
            exp = int(parsed.claims["exp"])
            iat = int(parsed.claims["iat"])
        except (JoseError, ValueError, TypeError, KeyError) as exc:
            raise InvalidAccessTokenError() from exc

        return AccessTokenClaims(
            sub=sub,
            role=role,
            jti=jti,
            exp=exp,
            iat=iat,
        )
