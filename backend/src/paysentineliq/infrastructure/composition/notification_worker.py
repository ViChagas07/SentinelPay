from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from paysentineliq.application.notifications.delivery import (
    NotificationDeliveryHandler,
)
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.db.repositories.notifications import (
    SqlAlchemyNotificationDeliveryRepository,
)
from paysentineliq.infrastructure.notifications.console import (
    ConsoleSmsAdapter,
    ConsoleWhatsAppAdapter,
)
from paysentineliq.infrastructure.notifications.email import SmtpEmailAdapter
from paysentineliq.infrastructure.security.destination_cipher import DestinationCipher


@asynccontextmanager
async def build_notification_runtime(
    settings: Settings,
) -> AsyncIterator[NotificationDeliveryHandler]:
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        repository = SqlAlchemyNotificationDeliveryRepository(
            session_factory,
            DestinationCipher(settings.security_hash_secret),
        )
        handler = NotificationDeliveryHandler(
            repository,
            SmtpEmailAdapter(
                host=settings.smtp_host,
                port=settings.smtp_port,
                sender=settings.smtp_from,
                username=settings.smtp_username,
                password=settings.smtp_password,
                starttls=settings.smtp_starttls,
                timeout=settings.smtp_timeout_seconds,
            ),
            ConsoleSmsAdapter(),
            ConsoleWhatsAppAdapter(),
        )
        yield handler
    finally:
        await engine.dispose()
