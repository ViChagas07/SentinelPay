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
