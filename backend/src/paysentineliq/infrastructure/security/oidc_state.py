import json
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from paysentineliq.application.errors import SecurityServiceUnavailableError
from paysentineliq.application.ports.oidc_state import OIDCState

_logger = logging.getLogger("paysentineliq")


class RedisOIDCStateStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def redis_key(self, state: str) -> str:
        return f"oidc:state:{state}"

    async def save(
        self,
        state: str,
        data: OIDCState,
        ttl_seconds: int,
    ) -> None:
        payload = json.dumps(
            {
                "nonce": data.nonce,
                "code_verifier": data.code_verifier,
                "redirect_uri": data.redirect_uri,
            }
        )
        try:
            await self._redis.set(
                self.redis_key(state),
                payload,
                ex=ttl_seconds,
            )
        except RedisError as exc:
            _logger.error("oidc_state_store_failure")
            raise SecurityServiceUnavailableError() from exc

    async def pop(self, state: str) -> OIDCState | None:
        try:
            raw = await self._redis.getdel(self.redis_key(state))
        except RedisError as exc:
            _logger.error("oidc_state_store_failure")
            raise SecurityServiceUnavailableError() from exc

        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None

        nonce = data.get("nonce")
        code_verifier = data.get("code_verifier")
        redirect_uri = data.get("redirect_uri")
        if not (
            isinstance(nonce, str)
            and isinstance(code_verifier, str)
            and isinstance(redirect_uri, str)
        ):
            return None

        return OIDCState(
            nonce=nonce,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
        )
