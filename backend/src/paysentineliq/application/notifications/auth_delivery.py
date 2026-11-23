import asyncio
import logging

from paysentineliq.application.notifications.auth_emails import AuthEmail
from paysentineliq.application.ports.messaging import EmailPort

_logger = logging.getLogger("paysentineliq")


async def deliver_auth_email(
    sender: EmailPort,
    email: AuthEmail,
    *,
    max_attempts: int = 3,
) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            await sender.send(
                to=email.to,
                subject=email.subject,
                body=email.text_body,
                html_body=email.html_body,
            )
            _logger.info("auth_email_sent kind=%s", email.kind)
            return True
        except Exception:
            _logger.warning(
                "auth_email_failed kind=%s attempt=%s",
                email.kind,
                attempt,
            )
            if attempt < max_attempts:
                await asyncio.sleep(0.5 * attempt)

    return False
