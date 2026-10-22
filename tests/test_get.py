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
