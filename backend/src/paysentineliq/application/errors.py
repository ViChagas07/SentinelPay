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
