import asyncio
import logging
import secrets
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

_logger = logging.getLogger("paysentineliq")


def mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    if not domain:
        return "***"
    visible = local[:1] if local else ""
    return f"{visible}***@{domain}"


class DevelopmentAuthEmailSender:
    def __init__(self, *, directory: Path) -> None:
        self._directory = directory

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        await asyncio.to_thread(self._write, to, subject, body, html_body)

    def _write(self, to: str, subject: str, body: str, html_body: str | None) -> None:
        message = EmailMessage()
        message["From"] = "no-reply@sentinelpay.local"
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
        message.set_content(body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        self._directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        path = self._directory / f"{stamp}-{secrets.token_hex(4)}.eml"
        path.write_bytes(message.as_bytes())
        _logger.info(
            "auth_email_outbox_written to=%s subject=%s path=%s",
            mask_email(to),
            subject,
            str(path),
        )
