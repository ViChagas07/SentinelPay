from typing import Protocol


class EmailPort(Protocol):
    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None: ...


class SmsPort(Protocol):
    async def send(self, *, to: str, body: str) -> None: ...


class WhatsAppPort(Protocol):
    async def send(self, *, to: str, body: str) -> None: ...
