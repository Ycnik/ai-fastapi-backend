"""Integrationstests für Optimistic Locking bei PUT."""

import pytest
from httpx import AsyncClient


def payload() -> dict[str, object]:
    return {
        "vorname": "Test",
        "nachname": "Person",
        "geburtsdatum": "2000-01-01",
        "geschlecht": "WEIBLICH",
        "rang": "REKRUT",
        "username": "test.put",
        "ausruestung": {"waffe": "Klinge", "seriennummer": "AOT-TESTPUT"},
        "verletzungen": [],
    }


@pytest.mark.asyncio
async def test_put_verhindert_lost_update(
    client: AsyncClient, test_soldat: None, admin_headers: dict[str, str]
) -> None:
    created = await client.post("/soldaten", json=payload(), headers=admin_headers)
    soldat_id = created.json()["id"]
    first = await client.get(f"/soldaten/{soldat_id}", headers=admin_headers)
    second = await client.get(f"/soldaten/{soldat_id}", headers=admin_headers)
    update_payload = payload()
    update_payload["nachname"] = "Aktualisiert"

    success = await client.put(
        f"/soldaten/{soldat_id}",
        headers={**admin_headers, "If-Match": first.headers["etag"]},
        json=update_payload,
    )
    assert success.status_code == 204
    assert success.headers["etag"] == '"1"'

    stale = await client.put(
        f"/soldaten/{soldat_id}",
        headers={**admin_headers, "If-Match": second.headers["etag"]},
        json=update_payload,
    )
    assert stale.status_code == 412


@pytest.mark.asyncio
async def test_put_prueft_if_match_und_existenz(
    client: AsyncClient, test_soldat: None, admin_headers: dict[str, str]
) -> None:
    created = await client.post("/soldaten", json=payload(), headers=admin_headers)
    soldat_id = created.json()["id"]

    missing_header = await client.put(
        f"/soldaten/{soldat_id}", headers=admin_headers, json=payload()
    )
    assert missing_header.status_code == 428

    invalid_header = await client.put(
        f"/soldaten/{soldat_id}",
        headers={**admin_headers, "If-Match": "invalid"},
        json=payload(),
    )
    assert invalid_header.status_code == 412

    missing = await client.put(
        "/soldaten/999999", headers={**admin_headers, "If-Match": '"0"'}, json=payload()
    )
    assert missing.status_code == 404
