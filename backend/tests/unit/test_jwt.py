import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from joserfc import jwt
from joserfc.jwk import OctKey

from paysentineliq.application.errors import InvalidAccessTokenError
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService

pytestmark = pytest.mark.unit

_SECRET = "s" * 64
_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _user(role: Role = Role.USER) -> User:
    from uuid import uuid4

    return User(
        id=uuid4(),
        google_sub="google-sub",
        email="user@example.com",
        name="User",
        preferred_locale="pt-BR",
        timezone="America/Sao_Paulo",
        role=role,
    )


def _service(*, clock: datetime = _BASE_TIME) -> JwtAccessTokenService:
    return JwtAccessTokenService(
        secret=_SECRET,
        ttl_minutes=15,
        clock=lambda: clock,
    )


def _b64(value: dict[str, object]) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_issue_and_decode_claims() -> None:
    user = _user(Role.ADMIN)
    service = _service()

    issued = service.issue(user)
    claims = service.decode(issued.token)

    assert claims.sub == user.id
    assert claims.role is Role.ADMIN
    assert claims.jti
    assert claims.iat == int(_BASE_TIME.timestamp())
    assert claims.exp == claims.iat + 900
    assert issued.expires_in_seconds == 900


def test_tampered_token_is_rejected() -> None:
    issued = _service().issue(_user())
    header, payload, signature = issued.token.split(".")
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = ".".join([header, tampered_payload, signature])

    with pytest.raises(InvalidAccessTokenError):
        _service().decode(tampered)


def test_expired_token_is_rejected() -> None:
    issued = _service(clock=_BASE_TIME).issue(_user())
    later = _BASE_TIME + timedelta(minutes=16)

    with pytest.raises(InvalidAccessTokenError):
        _service(clock=later).decode(issued.token)


def test_algorithm_swap_is_rejected() -> None:
    user = _user()
    claims = {
        "sub": str(user.id),
        "role": "user",
        "jti": "test-jti",
        "exp": int(_BASE_TIME.timestamp()) + 900,
        "iat": int(_BASE_TIME.timestamp()),
    }
    key = OctKey.import_key(_SECRET)
    token = jwt.encode({"alg": "HS512"}, claims, key, algorithms=["HS512"])

    with pytest.raises(InvalidAccessTokenError):
        _service().decode(token)


def test_none_algorithm_is_rejected() -> None:
    user = _user()
    claims = {
        "sub": str(user.id),
        "role": "user",
        "jti": "test-jti",
        "exp": int(_BASE_TIME.timestamp()) + 900,
        "iat": int(_BASE_TIME.timestamp()),
    }
    token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}."

    with pytest.raises(InvalidAccessTokenError):
        _service().decode(token)


def test_invalid_role_is_rejected() -> None:
    user = _user()
    claims = {
        "sub": str(user.id),
        "role": "root",
        "jti": "test-jti",
        "exp": int(_BASE_TIME.timestamp()) + 900,
        "iat": int(_BASE_TIME.timestamp()),
    }
    token = jwt.encode(
        {"alg": "HS256"},
        claims,
        OctKey.import_key(_SECRET),
    )

    with pytest.raises(InvalidAccessTokenError):
        _service().decode(token)


def test_missing_role_is_rejected() -> None:
    user = _user()
    claims = {
        "sub": str(user.id),
        "jti": "test-jti",
        "exp": int(_BASE_TIME.timestamp()) + 900,
        "iat": int(_BASE_TIME.timestamp()),
    }
    token = jwt.encode(
        {"alg": "HS256"},
        claims,
        OctKey.import_key(_SECRET),
    )

    with pytest.raises(InvalidAccessTokenError):
        _service().decode(token)
