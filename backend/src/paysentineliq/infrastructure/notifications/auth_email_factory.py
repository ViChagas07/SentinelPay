from pathlib import Path

from paysentineliq.application.ports.messaging import EmailPort
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.notifications.development_email import (
    DevelopmentAuthEmailSender,
)
from paysentineliq.infrastructure.notifications.email import SmtpEmailAdapter


def build_auth_email_sender(settings: Settings) -> EmailPort | None:
    if not settings.password_auth_enabled:
        return None
    if settings.auth_email_provider == "development":
        return DevelopmentAuthEmailSender(
            directory=Path(settings.auth_email_development_dir),
        )
    if settings.auth_email_provider == "smtp":
        return SmtpEmailAdapter(
            host=settings.smtp_host,
            port=settings.smtp_port,
            sender=settings.smtp_from,
            username=settings.smtp_username,
            password=settings.smtp_password,
            starttls=settings.smtp_starttls,
            timeout=settings.smtp_timeout_seconds,
        )
    return None
