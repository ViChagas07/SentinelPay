from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from paysentineliq.application.commands.auth import AuthService
from paysentineliq.application.commands.create_analysis import CreateAnalysisHandler
from paysentineliq.application.commands.documents import (
    DocumentPreparer,
    UploadDocumentHandler,
)
from paysentineliq.application.errors import (
    ForbiddenError,
    InvalidAccessTokenError,
    StorageNotConfiguredError,
)
from paysentineliq.application.locale import resolve_locale
from paysentineliq.application.ports.analysis import AnalysisLookupPort
from paysentineliq.application.ports.analysis_read_repository import (
    AnalysisReadRepositoryPort,
)
from paysentineliq.application.ports.analysis_unit_of_work import AnalysisUnitOfWork
from paysentineliq.application.ports.auth_unit_of_work import AuthUnitOfWork
from paysentineliq.application.ports.document_inspector import DocumentInspector
from paysentineliq.application.ports.document_read_repository import DocumentReadRepository
from paysentineliq.application.ports.document_unit_of_work import DocumentUnitOfWork
from paysentineliq.application.ports.oidc import OIDCClient
from paysentineliq.application.ports.oidc_state import OIDCStateStore
from paysentineliq.application.ports.readiness import ReadinessChecker
from paysentineliq.application.ports.repository import ExampleRepository
from paysentineliq.application.ports.revoked_tokens import RevokedTokenStore
from paysentineliq.application.ports.storage import StoragePort
from paysentineliq.application.ports.task_dispatcher import TaskDispatcherPort
from paysentineliq.application.ports.token_service import (
    AccessTokenClaims,
    AccessTokenService,
)
from paysentineliq.application.queries.analyses import (
    GetAnalysisHandler,
    ListAnalysesHandler,
)
from paysentineliq.application.queries.documents import GetDocumentDownloadUrlHandler
from paysentineliq.application.queries.example import GetExampleHandler
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.db.repositories.analyses import (
    SqlAlchemyAnalysisRepository,
)
from paysentineliq.infrastructure.db.repositories.analysis_read import (
    SqlAlchemyAnalysisReadRepository,
)
from paysentineliq.infrastructure.db.repositories.documents import (
    SqlAlchemyDocumentReadRepository,
)
from paysentineliq.infrastructure.db.repositories.example import (
    SqlAlchemyExampleRepository,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork
from paysentineliq.infrastructure.messaging.celery_app import build_celery_app
from paysentineliq.infrastructure.messaging.dispatcher import CeleryTaskDispatcher
from paysentineliq.infrastructure.readiness import SqlAlchemyRedisReadinessChecker
from paysentineliq.infrastructure.security.bruteforce import BruteForceService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_auth_unit_of_work(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthUnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_document_unit_of_work(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentUnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_analysis_unit_of_work(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnalysisUnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_task_dispatcher(request: Request) -> TaskDispatcherPort:
    dispatcher: TaskDispatcherPort | None = getattr(
        request.app.state,
        "task_dispatcher",
        None,
    )
    if dispatcher is None:
        settings: Settings = request.app.state.settings
        dispatcher = CeleryTaskDispatcher(build_celery_app(settings))
        request.app.state.task_dispatcher = dispatcher
    return dispatcher


def get_analysis_lookup(request: Request) -> AnalysisLookupPort:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return SqlAlchemyAnalysisRepository(session_factory)


def get_example_read_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExampleRepository:
    return SqlAlchemyExampleRepository(session)


def get_example_query(
    repository: Annotated[ExampleRepository, Depends(get_example_read_repository)],
) -> GetExampleHandler:
    return GetExampleHandler(repository)


def get_readiness_checker(request: Request) -> ReadinessChecker:
    engine: AsyncEngine = request.app.state.engine
    redis: Redis = request.app.state.redis
    return SqlAlchemyRedisReadinessChecker(engine, redis)


def get_locale(
    accept_language: Annotated[str | None, Header(alias="Accept-Language")] = None,
) -> str:
    return resolve_locale(accept_language)


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_token_service(request: Request) -> AccessTokenService:
    service: AccessTokenService = request.app.state.token_service
    return service


def get_revoked_token_store(request: Request) -> RevokedTokenStore:
    store: RevokedTokenStore = request.app.state.revoked_tokens
    return store


def get_oidc_client(request: Request) -> OIDCClient:
    client: OIDCClient = request.app.state.oidc_client
    return client


def get_oidc_state_store(request: Request) -> OIDCStateStore:
    store: OIDCStateStore = request.app.state.oidc_state_store
    return store


def get_brute_force(request: Request) -> BruteForceService:
    service: BruteForceService = request.app.state.brute_force
    return service


def get_storage(request: Request) -> StoragePort:
    storage: StoragePort | None = request.app.state.storage
    if storage is None:
        raise StorageNotConfiguredError()
    return storage


def get_document_inspector(request: Request) -> DocumentInspector:
    inspector: DocumentInspector = request.app.state.document_inspector
    return inspector


def get_upload_document_handler(
    uow: Annotated[
        DocumentUnitOfWork,
        Depends(get_document_unit_of_work),
    ],
    storage: Annotated[StoragePort, Depends(get_storage)],
    inspector: Annotated[DocumentInspector, Depends(get_document_inspector)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> UploadDocumentHandler:
    return UploadDocumentHandler(
        uow,
        storage,
        inspector,
        max_bytes=settings.upload_max_mb * 1024 * 1024,
        max_pdf_pages=settings.pdf_max_pages,
    )


def get_create_analysis_handler(
    uow: Annotated[AnalysisUnitOfWork, Depends(get_analysis_unit_of_work)],
    storage: Annotated[StoragePort, Depends(get_storage)],
    inspector: Annotated[DocumentInspector, Depends(get_document_inspector)],
    dispatcher: Annotated[TaskDispatcherPort, Depends(get_task_dispatcher)],
    lookup: Annotated[AnalysisLookupPort, Depends(get_analysis_lookup)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> CreateAnalysisHandler:
    return CreateAnalysisHandler(
        uow,
        DocumentPreparer(
            storage,
            inspector,
            max_bytes=settings.upload_max_mb * 1024 * 1024,
            max_pdf_pages=settings.pdf_max_pages,
        ),
        lookup,
        dispatcher,
        max_concurrent_per_user=settings.analysis_max_concurrent_per_user,
    )


def get_document_read_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentReadRepository:
    return SqlAlchemyDocumentReadRepository(session)


def get_analysis_read_repository(
    request: Request,
) -> AnalysisReadRepositoryPort:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return SqlAlchemyAnalysisReadRepository(session_factory)


def get_analysis_detail_query(
    repository: Annotated[
        AnalysisReadRepositoryPort,
        Depends(get_analysis_read_repository),
    ],
    storage: Annotated[StoragePort, Depends(get_storage)],
) -> GetAnalysisHandler:
    return GetAnalysisHandler(repository, storage)


def get_analysis_list_query(
    repository: Annotated[
        AnalysisReadRepositoryPort,
        Depends(get_analysis_read_repository),
    ],
) -> ListAnalysesHandler:
    return ListAnalysesHandler(repository)


def get_document_download_query(
    repository: Annotated[
        DocumentReadRepository,
        Depends(get_document_read_repository),
    ],
    storage: Annotated[StoragePort, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> GetDocumentDownloadUrlHandler:
    return GetDocumentDownloadUrlHandler(
        repository,
        storage,
        presigned_ttl_seconds=settings.s3_presigned_url_ttl_seconds,
    )


def get_auth_service(
    uow: Annotated[AuthUnitOfWork, Depends(get_auth_unit_of_work)],
    token_service: Annotated[AccessTokenService, Depends(get_token_service)],
    revoked: Annotated[RevokedTokenStore, Depends(get_revoked_token_store)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AuthService:
    return AuthService(
        uow,
        token_service,
        revoked,
        refresh_ttl_days=settings.refresh_token_ttl_days,
    )


def get_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization:
        raise InvalidAccessTokenError()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise InvalidAccessTokenError()
    return token.strip()


async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(get_bearer_token)],
    token_service: Annotated[AccessTokenService, Depends(get_token_service)],
    revoked: Annotated[RevokedTokenStore, Depends(get_revoked_token_store)],
    uow: Annotated[AuthUnitOfWork, Depends(get_auth_unit_of_work)],
) -> User:
    claims = token_service.decode(token)
    if await revoked.is_revoked(claims.jti):
        raise InvalidAccessTokenError()

    async with uow:
        user = await uow.users.get_by_id(claims.sub)

    if user is None:
        raise InvalidAccessTokenError()

    request.state.user_id = str(user.id)
    request.state.role = user.role.value
    return user


def get_optional_access_claims(
    token_service: Annotated[AccessTokenService, Depends(get_token_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> AccessTokenClaims | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    try:
        return token_service.decode(token.strip())
    except InvalidAccessTokenError:
        return None


def require_role(
    *allowed: Role,
) -> Callable[[User], Awaitable[User]]:
    allowed_roles = frozenset(allowed)

    async def dependency(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed_roles:
            raise ForbiddenError()
        return user

    return dependency
