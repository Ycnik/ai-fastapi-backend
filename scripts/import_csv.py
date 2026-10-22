"""Importiert die drei Soldaten-CSV-Dateien in PostgreSQL."""

import asyncio
import csv
import ssl
from datetime import date, datetime
from pathlib import Path

import asyncpg

from soldat.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "extras" / "postgres" / "init" / "soldat" / "csv"


def ssl_context() -> ssl.SSLContext | None:
    settings = get_settings()
    if not settings.db_ssl:
        return None
    context = ssl.create_default_context()
    if settings.db_ssl_cert_path and settings.db_ssl_cert_path.exists():
        context.load_verify_locations(cafile=str(settings.db_ssl_cert_path))
    if not settings.db_ssl_verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def rows(filename: str) -> list[dict[str, str]]:
    with (CSV_DIR / filename).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=";"))


async def main() -> None:
    """Leert abhängige Tabellen, importiert CSVs und korrigiert die Identitäten."""
    settings = get_settings()
    connection = await asyncpg.connect(
        settings.database_url.replace("+asyncpg", ""), ssl=ssl_context()
    )
    try:
        async with connection.transaction():
            await connection.execute(
                "TRUNCATE soldat.verletzung, soldat.ausruestung, soldat.soldat CASCADE"
            )
            for item in rows("soldat.csv"):
                await connection.execute(
                    """INSERT INTO soldat.soldat
                    (id, version, vorname, nachname, geburtsdatum, geschlecht, rang,
                     username, erzeugt, aktualisiert)
                    OVERRIDING SYSTEM VALUE
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                    int(item["id"]),
                    int(item["version"]),
                    item["vorname"],
                    item["nachname"],
                    date.fromisoformat(item["geburtsdatum"]),
                    item["geschlecht"],
                    item["rang"],
                    item["username"],
                    datetime.fromisoformat(item["erzeugt"]),
                    datetime.fromisoformat(item["aktualisiert"]),
                )
            for item in rows("ausruestung.csv"):
                await connection.execute(
                    """INSERT INTO soldat.ausruestung
                    (id, waffe, seriennummer, soldat_id)
                    OVERRIDING SYSTEM VALUE
                    VALUES ($1, $2, $3, $4)""",
                    int(item["id"]),
                    item["waffe"],
                    item["seriennummer"],
                    int(item["soldat_id"]),
                )
            for item in rows("verletzung.csv"):
                await connection.execute(
                    """INSERT INTO soldat.verletzung
                    (id, verletzungsbezeichnung, behandelt, schweregrad,
                     verletzungsdatum, soldat_id)
                    OVERRIDING SYSTEM VALUE
                    VALUES ($1, $2, $3, $4, $5, $6)""",
                    int(item["id"]),
                    item["verletzungsbezeichnung"],
                    item["behandelt"].lower() == "true",
                    item["schweregrad"],
                    date.fromisoformat(item["verletzungsdatum"]),
                    int(item["soldat_id"]),
                )
            for table in ("soldat", "ausruestung", "verletzung"):
                sequence_sql = (
                    "SELECT setval(pg_get_serial_sequence('soldat.{table}', 'id'), "
                    "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM soldat.{table}"
                )
                await connection.execute(sequence_sql.format(table=table))
    finally:
        await connection.close()
    print("CSV-Import erfolgreich abgeschlossen.")


if __name__ == "__main__":
    asyncio.run(main())
