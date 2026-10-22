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
async def test_put_verhindert_lost_update(client: AsyncClient, test_soldat: None) -> None:
    created = await client.post("/soldaten", json=payload())
    soldat_id = created.json()["id"]
    first = await client.get(f"/soldaten/{soldat_id}")
    second = await client.get(f"/soldaten/{soldat_id}")
    update_payload = payload()
    update_payload["nachname"] = "Aktualisiert"

    success = await client.put(
        f"/soldaten/{soldat_id}", headers={"If-Match": first.headers["etag"]}, json=update_payload
    )
    assert success.status_code == 204
    assert success.headers["etag"] == '"1"'

    stale = await client.put(
        f"/soldaten/{soldat_id}", headers={"If-Match": second.headers["etag"]}, json=update_payload
    )
    assert stale.status_code == 412
