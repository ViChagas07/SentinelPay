import base64
import json
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import OctKey, RSAKey

from paysentineliq.application.errors import (
    EmailNotVerifiedError,
    OAuthAuthenticationError,
)
from paysentineliq.application.ports.oidc import GoogleIdentity
from paysentineliq.infrastructure.security.google_oidc import GoogleOIDCClient

pytestmark = pytest.mark.unit

_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)
_CLIENT_ID = "test-client"
_REDIRECT_URI = "https://app.example/api/v1/auth/google/callback"
_ISSUER = "https://accounts.google.com"
_RSA_KEY = RSAKey.generate_key(2048, private=True, auto_kid=True)
_OCT_KEY = OctKey.import_key("x" * 64)


def _b64(value: dict[str, object]) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _claims(**overrides: object) -> dict[str, object]:
    now = int(_BASE_TIME.timestamp())
    claims: dict[str, object] = {
        "iss": _ISSUER,
        "aud": _CLIENT_ID,
        "sub": "google-sub",
        "email": "user@example.com",
        "email_verified": True,
        "name": "User",
        "nonce": "test-nonce",
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return claims


def _rs256_token(claims: dict[str, object]) -> str:
    header = {"alg": "RS256", "kid": _RSA_KEY.kid}
    return jwt.encode(header, claims, _RSA_KEY, algorithms=["RS256"])


def _client(id_token: str | None = None) -> GoogleOIDCClient:
    jwks = {"keys": [_RSA_KEY.as_dict(private=False)]}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            if id_token is None:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(
                200,
                json={
                    "access_token": "google-access",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "id_token": id_token,
                },
            )
        if request.url.path == "/certs":
            return httpx.Response(200, json=jwks)
        return httpx.Response(404)

    return GoogleOIDCClient(
        client_id=_CLIENT_ID,
        client_secret="test-secret",
        redirect_uri=_REDIRECT_URI,
        authorization_endpoint="https://google.test/auth",
        token_endpoint="https://google.test/token",
        jwks_uri="https://google.test/certs",
        issuer=_ISSUER,
        transport=httpx.MockTransport(handler),
        clock=lambda: _BASE_TIME,
    )


async def _exchange(id_token: str) -> GoogleIdentity:
    return await _client(id_token).exchange_code(
        code="auth-code",
        code_verifier="verifier",
        redirect_uri=_REDIRECT_URI,
        expected_nonce="test-nonce",
    )


async def test_authorization_url_contains_pkce_state_and_nonce() -> None:
    url = await _client().authorization_url(
        state="state-value",
        nonce="test-nonce",
        code_verifier="verifier-value",
    )

    query = parse_qs(urlsplit(url).query)

    assert query["state"] == ["state-value"]
    assert query["nonce"] == ["test-nonce"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"]
    assert query["client_id"] == [_CLIENT_ID]
    assert query["redirect_uri"] == [_REDIRECT_URI]
    assert "openid" in " ".join(query["scope"])


async def test_valid_id_token_returns_identity() -> None:
    identity = await _exchange(_rs256_token(_claims()))

    assert identity.google_sub == "google-sub"
    assert identity.email == "user@example.com"
    assert identity.name == "User"


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://evil.example"},
        {"aud": "other-client"},
        {"nonce": "wrong-nonce"},
        {"email_verified": False},
        {"email": ""},
    ],
)
async def test_invalid_id_token_claims_are_rejected(
    overrides: dict[str, object],
) -> None:
    token = _rs256_token(_claims(**overrides))

    expected = (
        EmailNotVerifiedError
        if overrides.get("email_verified") is False
        else OAuthAuthenticationError
    )
    with pytest.raises(expected):
        await _exchange(token)


async def test_expired_id_token_is_rejected() -> None:
    now = int(_BASE_TIME.timestamp())
    token = _rs256_token(_claims(exp=now - 1))

    with pytest.raises(OAuthAuthenticationError):
        await _exchange(token)


async def test_tampered_id_token_is_rejected() -> None:
    token = _rs256_token(_claims())
    header, payload, signature = token.split(".")
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = ".".join([header, tampered_payload, signature])

    with pytest.raises(OAuthAuthenticationError):
        await _exchange(tampered)


async def test_algorithm_swap_is_rejected() -> None:
    token = jwt.encode(
        {"alg": "HS256"},
        _claims(),
        _OCT_KEY,
        algorithms=["HS256"],
    )

    with pytest.raises(OAuthAuthenticationError):
        await _exchange(token)


async def test_none_algorithm_is_rejected() -> None:
    token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(_claims())}."

    with pytest.raises(OAuthAuthenticationError):
        await _exchange(token)


async def test_token_endpoint_failure_is_rejected() -> None:
    with pytest.raises(OAuthAuthenticationError):
        await _client(None).exchange_code(
            code="auth-code",
            code_verifier="verifier",
            redirect_uri=_REDIRECT_URI,
            expected_nonce="test-nonce",
        )
