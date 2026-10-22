"""Gemeinsame Fixtures für Integrationstests gegen PostgreSQL."""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from soldat.db import session_factory
from soldat.main import app
from soldat.models import Soldat


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTPX-Client für die ASGI-Anwendung."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


@pytest_asyncio.fixture
async def test_soldat() -> AsyncIterator[None]:
    """Entfernt Testdatensätze vor und nach jedem Test."""
    async with session_factory() as session:
        await session.execute(delete(Soldat).where(Soldat.username.like("test.%")))
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(delete(Soldat).where(Soldat.username.like("test.%")))
        await session.commit()
