import logging
import smtplib
from email.message import EmailMessage
from typing import ClassVar

import pytest

from paysentineliq.infrastructure.notifications.console import (
    ConsoleSmsAdapter,
    ConsoleWhatsAppAdapter,
)
from paysentineliq.infrastructure.notifications.email import SmtpEmailAdapter

pytestmark = pytest.mark.unit


class FakeSmtp:
    instances: ClassVar[list["FakeSmtp"]] = []

    def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.message: EmailMessage | None = None
        FakeSmtp.instances.append(self)

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.message = message


async def test_smtp_adapter_sends_plain_text_email(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSmtp.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    adapter = SmtpEmailAdapter(
        host="mailpit",
        port=1025,
        sender="no-reply@paysentineliq.local",
        username="user",
        password="secret",
        starttls=True,
        timeout=5,
    )

    await adapter.send(
        to="destination@example.com",
        subject="Assunto",
        body="Mensagem mínima.",
    )

    smtp = FakeSmtp.instances[0]
    assert smtp.host == "mailpit"
    assert smtp.port == 1025
    assert smtp.started_tls is True
    assert smtp.login_args == ("user", "secret")
    assert smtp.message is not None
    message = smtp.message
    assert message.get_content_type() == "text/plain"
    payload = message.get_payload(decode=True)
    assert isinstance(payload, bytes)
    assert payload.decode().strip() == "Mensagem mínima."


async def test_console_sms_adapter_does_not_log_destination_or_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="paysentineliq")
    adapter = ConsoleSmsAdapter()

    await adapter.send(to="+5511999999999", body="conteudo sensivel do recibo")

    assert "sms_console_send" in caplog.text
    assert "+5511999999999" not in caplog.text
    assert "conteudo sensivel" not in caplog.text


async def test_console_whatsapp_adapter_does_not_log_destination_or_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="paysentineliq")
    adapter = ConsoleWhatsAppAdapter()

    await adapter.send(to="+5511888888888", body="conteudo sensivel do recibo")

    assert "whatsapp_console_send" in caplog.text
    assert "+5511888888888" not in caplog.text
    assert "conteudo sensivel" not in caplog.text
