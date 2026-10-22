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
async def test_post_soldat(client: AsyncClient, test_soldat: None) -> None:
    response = await client.post("/soldaten", json=payload())
    assert response.status_code == 201
    assert response.headers["location"].startswith("/soldaten/")
    assert response.json()["username"] == "test.post"


@pytest.mark.asyncio
async def test_post_validierung(client: AsyncClient, test_soldat: None) -> None:
    invalid = payload()
    invalid["geburtsdatum"] = "2999-01-01"
    response = await client.post("/soldaten", json=invalid)
    assert response.status_code == 422
