"""Gemeinsame Fixtures für Integrationstests gegen PostgreSQL."""

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from soldat.config import get_settings
from soldat.db import session_factory
from soldat.main import app
from soldat.models import Soldat


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTPX-Client für die ASGI-Anwendung."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value


async def _keycloak_token(username: str) -> str:
    """Holt einen echten Testtoken und meldet fehlendes Keycloak verständlich."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5) as keycloak:
            response = await keycloak.post(
                settings.keycloak_token_url,
                data={
                    "client_id": settings.keycloak_client_id,
                    "username": username,
                    "password": "p",
                    "grant_type": "password",
                },
            )
    except httpx.RequestError as exc:
        pytest.skip(f"Keycloak läuft nicht ({exc}); Security-Integrationstests übersprungen")
    if response.status_code != 200:
        pytest.fail(
            f"Keycloak-Token für {username} konnte nicht geholt werden: "
            f"HTTP {response.status_code} {response.text}"
        )
    token = response.json().get("access_token")
    if not isinstance(token, str) or not token:
        pytest.fail(f"Keycloak lieferte für {username} kein access_token")
    return token


@pytest_asyncio.fixture(scope="session")
async def admin_headers() -> dict[str, str]:
    """Session-cached Bearer-Header für den Testuser admin."""
    return {"Authorization": f"Bearer {await _keycloak_token('admin')}"}


@pytest_asyncio.fixture(scope="session")
async def user_headers() -> dict[str, str]:
    """Session-cached Bearer-Header für den Testuser user."""
    return {"Authorization": f"Bearer {await _keycloak_token('user')}"}


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
