"""Integrationstests für POST /soldaten."""

import pytest
from httpx import AsyncClient


def payload() -> dict[str, object]:
    return {
        "vorname": "Test",
        "nachname": "Person",
        "geburtsdatum": "2000-01-01",
        "geschlecht": "WEIBLICH",
        "rang": "REKRUT",
        "username": "test.post",
        "ausruestung": {"waffe": "Klinge", "seriennummer": "AOT-TESTPOST"},
        "verletzungen": [],
    }


@pytest.mark.asyncio
async def test_post_soldat(
    client: AsyncClient, test_soldat: None, admin_headers: dict[str, str]
) -> None:
    response = await client.post("/soldaten", json=payload(), headers=admin_headers)
    assert response.status_code == 201
    assert response.headers["location"].startswith("/soldaten/")
    assert response.json()["username"] == "test.post"


@pytest.mark.asyncio
async def test_post_validierung(
    client: AsyncClient, test_soldat: None, admin_headers: dict[str, str]
) -> None:
    invalid = payload()
    invalid["geburtsdatum"] = "2999-01-01"
    response = await client.post("/soldaten", json=invalid, headers=admin_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_duplikate_liefern_409(
    client: AsyncClient, test_soldat: None, admin_headers: dict[str, str]
) -> None:
    first = await client.post("/soldaten", json=payload(), headers=admin_headers)
    assert first.status_code == 201

    same_username = payload()
    same_username["ausruestung"] = {"waffe": "Schrotflinte", "seriennummer": "AOT-OTHER"}
    duplicate_username = await client.post("/soldaten", json=same_username, headers=admin_headers)
    assert duplicate_username.status_code == 409

    same_serial = payload()
    same_serial["username"] = "test.other"
    duplicate_serial = await client.post("/soldaten", json=same_serial, headers=admin_headers)
    assert duplicate_serial.status_code == 409
