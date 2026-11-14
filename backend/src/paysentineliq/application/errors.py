from paysentineliq.domain.errors import DomainError


class ApplicationError(DomainError):
    def __init__(
        self,
        *,
        code: str = "application_error",
        message: str = "Application operation failed.",
        status_code: int = 400,
        title: str = "Application error",
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=status_code,
            title=title,
        )


class CsrfError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="csrf_invalid",
            message="CSRF token is missing or invalid.",
            status_code=403,
            title="Forbidden",
        )


class SecurityServiceUnavailableError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="security_service_unavailable",
            message="Security service is unavailable.",
            status_code=503,
            title="Service unavailable",
        )


class SSRFBlockedError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="ssrf_blocked",
            message="URL is not allowed.",
            status_code=400,
            title="Bad request",
        )


class InvalidAccessTokenError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_access_token",
            message="Invalid or expired access token.",
            status_code=401,
            title="Unauthorized",
        )


class ForbiddenError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="forbidden",
            message="Insufficient permissions.",
            status_code=403,
            title="Forbidden",
        )


class AuthNotConfiguredError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="auth_not_configured",
            message="Authentication is not configured.",
            status_code=503,
            title="Service unavailable",
        )


class OAuthAuthenticationError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="google_auth_failed",
            message="Google authentication failed.",
            status_code=401,
            title="Unauthorized",
        )


class EmailNotVerifiedError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="email_not_verified",
            message="Google account email is not verified.",
            status_code=403,
            title="Forbidden",
        )


class InvalidOAuthStateError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_state",
            message="OAuth state is missing or invalid.",
            status_code=400,
            title="Bad request",
        )


class InvalidRefreshTokenError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_refresh_token",
            message="Refresh token is invalid or expired.",
            status_code=401,
            title="Unauthorized",
        )


class RefreshTokenReuseError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="refresh_token_reuse",
            message="Refresh token reuse detected.",
            status_code=401,
            title="Unauthorized",
        )


class TooManyAttemptsError(ApplicationError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            code="too_many_attempts",
            message="Too many attempts. Try again later.",
            status_code=429,
            title="Too many requests",
        )
        self.retry_after_seconds = retry_after_seconds
