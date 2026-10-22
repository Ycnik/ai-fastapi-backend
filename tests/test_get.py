"""Integrationstests für GET-Endpunkte."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_soldat_mit_etag(client: AsyncClient) -> None:
    response = await client.get("/soldaten/1")
    assert response.status_code == 200
    assert response.headers["etag"] == '"0"'
    assert response.json()["ausruestung"]["seriennummer"] == "AOT-543ABC"

    cached = await client.get("/soldaten/1", headers={"If-None-Match": '"0"'})
    assert cached.status_code == 304
    assert cached.content == b""


@pytest.mark.asyncio
async def test_get_soldaten_filter(client: AsyncClient) -> None:
    response = await client.get("/soldaten", params={"rang": "CAPTAIN", "limit": 10})
    assert response.status_code == 200
    assert [item["username"] for item in response.json()] == ["sophias"]


@pytest.mark.asyncio
async def test_get_soldat_und_verletzungen_404(client: AsyncClient) -> None:
    missing = await client.get("/soldaten/999999")
    assert missing.status_code == 404

    injuries = await client.get("/soldaten/1/verletzungen")
    assert injuries.status_code == 200
    assert injuries.json()[0]["verletzungsbezeichnung"] == "Knochenbruch"


@pytest.mark.asyncio
async def test_get_soldaten_pagination(client: AsyncClient) -> None:
    response = await client.get("/soldaten", params={"limit": 1, "offset": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1
