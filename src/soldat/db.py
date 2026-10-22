"""Asynchroner Datenbankzugriff mit TLS für PostgreSQL."""

import ssl
from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import Settings, get_settings


def create_ssl_context(settings: Settings) -> ssl.SSLContext | None:
    """Erzeugt den PostgreSQL-TLS-Kontext für die lokale Entwicklung."""
    if not settings.db_ssl:
        return None
    context = ssl.create_default_context()
    if settings.db_ssl_cert_path and settings.db_ssl_cert_path.exists():
        context.load_verify_locations(cafile=str(settings.db_ssl_cert_path))
    if not settings.db_ssl_verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Erstellt die Session-Fabrik, die in der App verwendet wird."""
    connect_args: dict[str, object] = {}
    ssl_context = create_ssl_context(settings)
    if ssl_context is not None:
        connect_args["ssl"] = ssl_context
    engine = create_async_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


session_factory = create_session_factory(get_settings())


async def get_session(
    factory: async_sessionmaker[AsyncSession] = Depends(lambda: session_factory),
) -> AsyncIterator[AsyncSession]:
    """FastAPI-Dependency für eine transaktional nutzbare DB-Session."""
    async with factory() as session:
        yield session
