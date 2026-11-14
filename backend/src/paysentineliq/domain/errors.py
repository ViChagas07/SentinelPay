class DomainError(Exception):
    def __init__(
        self,
        *,
        code: str = "domain_error",
        message: str = "Domain rule violated.",
        status_code: int = 422,
        title: str = "Domain error",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.title = title


class NotFoundError(DomainError):
    def __init__(
        self,
        *,
        code: str = "not_found",
        message: str = "Resource not found.",
        title: str = "Not found",
    ) -> None:
        super().__init__(code=code, message=message, status_code=404, title=title)
