from paysentineliq.domain.errors import DomainError, NotFoundError


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


class UploadTooLargeError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="upload_too_large",
            message="Upload exceeds the allowed size.",
            status_code=413,
            title="Payload too large",
        )


class EmptyDocumentError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="empty_document",
            message="Uploaded document is empty.",
            status_code=422,
            title="Unprocessable entity",
        )


class UnsupportedDocumentTypeError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="unsupported_document_type",
            message="Only PDF, PNG and JPEG are accepted.",
            status_code=422,
            title="Unprocessable entity",
        )


class InvalidDocumentError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_document",
            message="Document content is invalid.",
            status_code=422,
            title="Unprocessable entity",
        )


class PdfPageLimitError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="pdf_page_limit_exceeded",
            message="PDF exceeds the allowed page count.",
            status_code=422,
            title="Unprocessable entity",
        )


class EncryptedPdfError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="encrypted_pdf",
            message="Encrypted PDF is not accepted.",
            status_code=422,
            title="Unprocessable entity",
        )


class DangerousPdfError(ApplicationError):
    def __init__(self, evidence: tuple[str, ...]) -> None:
        super().__init__(
            code="pdf_active_content",
            message="PDF contains active or embedded content.",
            status_code=422,
            title="Unprocessable entity",
        )
        self.evidence = evidence


class StorageNotConfiguredError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="storage_not_configured",
            message="Document storage is not configured.",
            status_code=503,
            title="Service unavailable",
        )


class StorageUnavailableError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="storage_unavailable",
            message="Document storage is unavailable.",
            status_code=503,
            title="Service unavailable",
        )


class DocumentNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(
            code="document_not_found",
            message="Document not found.",
        )


class UnsupportedDocumentError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="unsupported_document",
            message="Document format is not supported for ingestion.",
            status_code=422,
            title="Unprocessable entity",
        )


class InvalidIdempotencyKeyError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_idempotency_key",
            message="Idempotency-Key must have 8 to 128 safe characters.",
            status_code=422,
            title="Unprocessable entity",
        )


class IdempotencyConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="idempotency_conflict",
            message="Idempotency-Key was already used with another request.",
            status_code=409,
            title="Conflict",
        )


class AnalysisQuotaExceededError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="analysis_quota_exceeded",
            message="Too many concurrent analyses for this user.",
            status_code=429,
            title="Too many requests",
        )


class TaskDispatchError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="task_dispatch_failed",
            message="Analysis queue is unavailable.",
            status_code=503,
            title="Service unavailable",
        )


class NotificationNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(
            code="notification_not_found",
            message="Notification not found.",
        )


class InvalidLocaleError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_locale",
            message="Locale is not supported.",
            status_code=422,
            title="Unprocessable entity",
        )


class InvalidNotificationPreferenceError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_notification_preference",
            message="Notification preference is invalid.",
            status_code=422,
            title="Unprocessable entity",
        )


class PayableNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(
            code="payable_not_found",
            message="Payable not found.",
        )


class PayableStateError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="payable_invalid_state",
            message="Payable cannot transition from its current state.",
            status_code=409,
            title="Conflict",
        )


class AnalysisNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(
            code="analysis_not_found",
            message="Analysis not found.",
        )


class InvalidCursorError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="invalid_cursor",
            message="Cursor is invalid.",
            status_code=422,
            title="Unprocessable entity",
        )


class OcrUnavailableError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="ocr_unavailable",
            message="OCR engine is unavailable.",
            status_code=503,
            title="Service unavailable",
        )


class OcrTimeoutError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="ocr_timeout",
            message="OCR processing timed out.",
            status_code=504,
            title="Gateway timeout",
        )


class OcrPageLimitError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="ocr_page_limit_exceeded",
            message="Document exceeds the OCR page limit.",
            status_code=422,
            title="Unprocessable entity",
        )


class OcrImageTooLargeError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="ocr_image_too_large",
            message="Rendered page exceeds the image size limit.",
            status_code=422,
            title="Unprocessable entity",
        )


class RagUnavailableError(RuntimeError):
    pass


class EmbeddingDimensionError(ValueError):
    pass


class EmbeddingUnavailableError(RuntimeError):
    pass


class AnalysisTimeoutError(RuntimeError):
    def __init__(self, node: str) -> None:
        super().__init__(f"analysis node timed out: {node}")
        self.node = node


class LlmUnavailableError(RuntimeError):
    pass


class GuardrailViolationError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            code="guardrail_violation",
            message="The request violates a guardrail policy.",
            status_code=422,
            title="Unprocessable entity",
        )
