import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from paysentineliq.application.ports.revoked_tokens import RevokedTokenStore
from paysentineliq.application.ports.token_service import AccessTokenService

_logger = logging.getLogger("paysentineliq")


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        token_service: AccessTokenService | None = getattr(request.app.state, "token_service", None)
        revoked: RevokedTokenStore | None = getattr(request.app.state, "revoked_tokens", None)
        authorization = request.headers.get("authorization")
        if token_service is not None and revoked is not None and authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() == "bearer" and token.strip():
                try:
                    claims = token_service.decode(token.strip())
                    if not await revoked.is_revoked(claims.jti):
                        request.state.user_id = str(claims.sub)
                        request.state.role = claims.role.value
                except Exception:
                    _logger.debug("auth_context_ignored")
        return await call_next(request)
