import logging

_logger = logging.getLogger("paysentineliq")


class ConsoleSmsAdapter:
    async def send(self, *, to: str, body: str) -> None:
        _logger.info("sms_console_send")


class ConsoleWhatsAppAdapter:
    async def send(self, *, to: str, body: str) -> None:
        _logger.info("whatsapp_console_send")
