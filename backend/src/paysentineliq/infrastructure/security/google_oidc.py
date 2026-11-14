import hmac
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry

from paysentineliq.application.errors import (
    EmailNotVerifiedError,
    OAuthAuthenticationError,
)
from paysentineliq.application.ports.oidc import GoogleIdentity


class GoogleOIDCClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        authorization_endpoint: str,
        token_endpoint: str,
        jwks_uri: str,
        issuer: str,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        jwks_ttl_seconds: int = 3600,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._authorization_endpoint = authorization_endpoint
        self._token_endpoint = token_endpoint
        self._jwks_uri = jwks_uri
        self._issuer = issuer
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._jwks_ttl_seconds = jwks_ttl_seconds
        self._keys: KeySet | None = None
        self._keys_expire_at = 0.0

    async def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str:
        try:
            async with AsyncOAuth2Client(
                client_id=self._client_id,
                client_secret=self._client_secret,
                redirect_uri=self._redirect_uri,
                scope="openid email profile",
                code_challenge_method="S256",
                transport=self._transport,
                timeout=5.0,
            ) as client:
                uri, _ = client.create_authorization_url(
                    self._authorization_endpoint,
                    state=state,
                    code_verifier=code_verifier,
                    nonce=nonce,
                )
                return str(uri)
        except Exception as exc:
            raise OAuthAuthenticationError() from exc

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        expected_nonce: str,
    ) -> GoogleIdentity:
        try:
            async with AsyncOAuth2Client(
                client_id=self._client_id,
                client_secret=self._client_secret,
                redirect_uri=self._redirect_uri,
                scope="openid email profile",
                code_challenge_method="S256",
                transport=self._transport,
                timeout=5.0,
            ) as client:
                token = await client.fetch_token(
                    self._token_endpoint,
                    code=code,
                    code_verifier=code_verifier,
                    redirect_uri=redirect_uri,
                    grant_type="authorization_code",
                )
        except Exception as exc:
            raise OAuthAuthenticationError() from exc

        id_token = token.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise OAuthAuthenticationError()

        return await self._verify_id_token(
            id_token,
            expected_nonce=expected_nonce,
        )

    async def _verify_id_token(
        self,
        id_token: str,
        *,
        expected_nonce: str,
    ) -> GoogleIdentity:
        keys = await self._load_keys()

        try:
            parsed = jwt.decode(
                id_token,
                keys,
                algorithms=["RS256"],
            )
            registry = JWTClaimsRegistry(
                now=int(self._clock().timestamp()),
                exp={"essential": True},
                iat={"essential": True},
            )
            registry.validate(parsed.claims)

            claims = parsed.claims
            if claims.get("iss") not in {
                self._issuer,
                "accounts.google.com",
            }:
                raise OAuthAuthenticationError()

            audience = claims.get("aud")
            if isinstance(audience, str):
                audience_ok = audience == self._client_id
            elif isinstance(audience, list):
                audience_ok = self._client_id in audience
            else:
                audience_ok = False
            if not audience_ok:
                raise OAuthAuthenticationError()

            nonce = claims.get("nonce")
            if not isinstance(nonce, str) or not hmac.compare_digest(
                nonce,
                expected_nonce,
            ):
                raise OAuthAuthenticationError()

            verified = claims.get("email_verified")
            if verified is False:
                raise EmailNotVerifiedError()
            if verified is not True:
                raise OAuthAuthenticationError()

            sub = claims.get("sub")
            email = claims.get("email")
            if not isinstance(sub, str) or not sub or not isinstance(email, str) or not email:
                raise OAuthAuthenticationError()

            name = claims.get("name")
            return GoogleIdentity(
                google_sub=sub,
                email=email,
                name=name if isinstance(name, str) else None,
            )
        except (JoseError, ValueError, TypeError, KeyError) as exc:
            raise OAuthAuthenticationError() from exc

    async def _load_keys(self) -> KeySet:
        now = time.monotonic()
        if self._keys is not None and now < self._keys_expire_at:
            return self._keys

        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=5.0,
            ) as client:
                response = await client.get(self._jwks_uri)
                response.raise_for_status()
                data: Any = response.json()
            keys = KeySet.import_key_set(data)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise OAuthAuthenticationError() from exc

        self._keys = keys
        self._keys_expire_at = now + self._jwks_ttl_seconds
        return keys
