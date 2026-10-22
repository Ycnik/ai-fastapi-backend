"""Integrationstests für Authentifizierung und Rollenrechte."""

import pytest
from httpx import AsyncClient


def payload() -> dict[str, object]:
    return {
        "vorname": "Security",
        "nachname": "Test",
        "geburtsdatum": "2000-01-01",
        "geschlecht": "WEIBLICH",
        "rang": "REKRUT",
        "username": "test.security",
        "ausruestung": {"waffe": "Klinge", "seriennummer": "AOT-SECURITY"},
        "verletzungen": [],
    }


@pytest.mark.asyncio
async def test_ohne_token_401(client: AsyncClient) -> None:
    response = await client.get("/soldaten/1")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_ungueltiges_token_401(client: AsyncClient) -> None:
    response = await client.get(
        "/soldaten/1", headers={"Authorization": "Bearer offensichtlich-ungueltig"}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_user_darf_get_inklusive_304_aber_nicht_schreiben(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.get("/soldaten/1", headers=user_headers)
    assert response.status_code == 200

    cached = await client.get(
        "/soldaten/1",
        headers={**user_headers, "If-None-Match": response.headers["etag"]},
    )
    assert cached.status_code == 304

    forbidden_post = await client.post("/soldaten", json=payload(), headers=user_headers)
    assert forbidden_post.status_code == 403

    forbidden_put = await client.put(
        "/soldaten/1",
        headers={**user_headers, "If-Match": response.headers["etag"]},
        json=payload(),
    )
    assert forbidden_put.status_code == 403
