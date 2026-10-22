# Soldat-Backend

Asynchrones REST-Backend für die Soldatenverwaltung mit FastAPI, SQLAlchemy 2.x,
PostgreSQL und Pydantic v2. Die Fachbegriffe und Datenbankwerte bleiben deutsch;
technische Bezeichner sind englisch.

## Voraussetzungen

- Python 3.12 oder neuer
- [uv](https://docs.astral.sh/uv/)
- Docker mit laufendem PostgreSQL-Container aus `extras/postgres/`

Keycloak, Authentifizierung und Rollen sind ausdrücklich nicht Bestandteil dieses
Projekts. Die Router nutzen FastAPI-Dependencies, sodass später eine
Security-Dependency ergänzt werden kann.

## Datenbank einrichten

Die vorhandene Docker-Konfiguration wird nicht verändert. Im Verzeichnis
`extras/postgres` werden die Volumes und der Container gestartet. Danach werden
Schema und Tabellen einmalig eingespielt:

```powershell
docker compose -f extras/postgres/compose.yml up -d
docker exec -i postgres psql -U postgres -d soldat -f /init/soldat/sql/create-schema.sql
docker exec -i postgres psql -U postgres -d soldat -f /init/soldat/sql/create-tables.sql
```

Falls die Datenbank noch nicht initialisiert wurde, sind `create-db.sql` und
`create-schema.sql` in der vorhandenen Initialisierungsstruktur auszuführen.
Die Testdaten werden mit `uv run python scripts/import_csv.py` importiert. Der
Import leert die drei Tabellen, importiert die CSV-Dateien wiederholbar und setzt
die Identity-Sequenzen hinter den höchsten IDs.

## Anwendung

```powershell
uv sync
Copy-Item .env.example .env
uv run uvicorn soldat.main:app --app-dir src --reload
```

Die lokale PostgreSQL-Verbindung nutzt TLS. Für das selbstsignierte Zertifikat
ist `DB_SSL_VERIFY=false` voreingestellt; für eine geprüfte Verbindung kann die
Option zusammen mit `DB_SSL_CERT` aktiviert werden.

## API

- `GET /health` liefert `{"status": "ok"}`.
- `GET /soldaten/{id}` liefert einen Soldaten inklusive Ausrüstung und Verletzungen
  sowie `ETag: "<version>"`. Ein passendes `If-None-Match` liefert `304`.
- `GET /soldaten` unterstützt `nachname`, `rang`, `geschlecht`, `waffe`,
  `schweregrad`, `limit` und `offset`. Keine Treffer werden konsistent als leere
  Liste mit `200` geliefert.
- `GET /soldaten/{id}/verletzungen` liefert die Verletzungen eines Soldaten.
- `POST /soldaten` legt Soldat, Pflichtausrüstung und optionale Verletzungen in
  einer Transaktion an. `Location` und `ETag` werden gesetzt; Duplikate liefern `409`.
- `PUT /soldaten/{id}` verlangt `If-Match`. Fehlende Header liefern `428`, eine
  veraltete Version `412`; das Update erfolgt atomar und liefert die neue `ETag`.

## Qualität und Tests

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

Die Integrationstests verwenden die echte PostgreSQL-Datenbank und räumen ihre
Testdaten wieder auf. Für die Endpunkte gibt es zusätzlich eine Bruno-Collection
unter `bruno/`.

