# Soldat-Backend

Asynchrones REST-Backend für die Soldatenverwaltung mit FastAPI, SQLAlchemy 2.x,
PostgreSQL und Pydantic v2. Die Fachbegriffe und Datenbankwerte bleiben deutsch;
technische Bezeichner sind englisch.

## Voraussetzungen

- Python 3.12 oder neuer
- [uv](https://docs.astral.sh/uv/)
- Docker mit laufendem PostgreSQL-Container aus `extras/postgres/`
- Docker mit Keycloak aus `keycloak/`

## Datenbank einrichten

Die vorhandene Docker-Konfiguration wird nicht verändert. Im Verzeichnis
`extras/postgres` werden die Volumes und der Container gestartet. Danach werden
Schema und Tabellen einmalig eingespielt:

```powershell
docker compose -f extras/postgres/compose.yml up -d
docker exec -i postgres psql -U postgres -d soldat -f /init/soldat/sql/create-schema.sql
docker cp extras/postgres/init/soldat/sql/create-tables.sql postgres:/tmp/create-tables.sql
docker exec -e PGPASSWORD=p postgres psql -U soldat -d soldat -f /tmp/create-tables.sql
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
docker compose -f extras/postgres/compose.yml up -d
docker compose --env-file .env -f keycloak/compose.yml up -d
uv run uvicorn soldat.main:app --app-dir src --reload
```

Die lokale PostgreSQL-Verbindung nutzt TLS. Für das selbstsignierte Zertifikat
ist `DB_SSL_VERIFY=false` voreingestellt; für eine geprüfte Verbindung kann die
Option zusammen mit `DB_SSL_CERT` aktiviert werden.

## Keycloak (lokal)

Keycloak läuft als eigener Docker-Stack und verwendet nicht die Soldat-Datenbank.
Die Compose-Datei importiert den Realm reproduzierbar aus
`keycloak/import/realm-export.json`:

```powershell
Copy-Item .env.example .env
docker compose --env-file .env -f keycloak/compose.yml up -d
```

Die lokalen Dummy-Zugangsdaten (`admin`/`p` und `user`/`p`) sind ausschließlich
für Entwicklung und Tests gedacht. Der Bootstrap-Admin wird über
`KEYCLOAK_ADMIN_USERNAME` und `KEYCLOAK_ADMIN_PASSWORD` aus `.env` gesetzt.

Der Realm-Import wurde mit Keycloak 26.8.1 erfolgreich geprüft. Der Password Grant
lieferte für beide Testuser HTTP 200 und Bearer-Tokens. Die geprüften Tokenwerte
waren `iss=http://localhost:8080/realms/soldat`, `azp=soldat-api`,
`aud=soldat-api`; die Realm-Rollen waren `admin` beziehungsweise `user`.

Tokenabruf per PowerShell mit `curl.exe`:

```powershell
$tokenUrl = "http://localhost:8080/realms/soldat/protocol/openid-connect/token"
curl.exe -X POST $tokenUrl `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "client_id=soldat-api&username=admin&password=p&grant_type=password"
curl.exe -X POST $tokenUrl `
  -H "Content-Type: application/x-www-form-urlencoded" `
  --data "client_id=soldat-api&username=user&password=p&grant_type=password"
```

Die Passwortwerte `p` und `admin-dev-only` sind Dummy-Werte ausschließlich für
die lokale Entwicklung. In einer echten Umgebung müssen sie ersetzt und niemals
committet werden.

### JWT-Prüfung

Die API lädt die JWKS asynchron von `KEYCLOAK_JWKS_URL` und cached die Schlüssel
für `KEYCLOAK_JWKS_CACHE_SECONDS`. Akzeptiert werden ausschließlich RS256-Tokens.
Geprüft werden Signatur, `exp`, `iss` sowie Audience oder `azp`. Issuer, JWKS-URL,
Client-ID und Audience kommen aus `.env` beziehungsweise `.env.example`.

### Rollenmatrix

| Endpunkt | `user` | `admin` |
| --- | ---: | ---: |
| `GET /soldaten` | Ja | Ja |
| `GET /soldaten/{id}` | Ja | Ja |
| `GET /soldaten/{id}/verletzungen` | Ja | Ja |
| `POST /soldaten` | Nein (403) | Ja |
| `PUT /soldaten/{id}` | Nein (403) | Ja |
| `GET /health` | Öffentlich | Öffentlich |

Ohne Token oder mit ungültigem Token antwortet die API mit `401` und
`WWW-Authenticate: Bearer`. Ein gültiges Token ohne benötigte Rolle liefert `403`.

### Bruno

1. Server und Keycloak starten.
2. Einmalig `bruno/environments/local.example.bru` nach
   `bruno/environments/local.bru` kopieren. Diese lokale Datei bleibt wegen der
   kurzlebigen Tokenwerte außerhalb von Git.
3. In Bruno die Collection `bruno/` und das Environment `local` öffnen.
4. `Token holen (admin)` oder `Token holen (user)` ausführen.
5. Die geschützten Requests verwenden danach automatisch den gespeicherten
   Bearer-Token. Die Requests `Ohne Token (401)`, `Ungültiges Token (401)` und
   `User schreibt (403)` zeigen die Fehlerfälle.

### Troubleshooting

- Der erste Start von Keycloak kann wegen Quarkus-Optimierung und H2-Initialisierung
  mehrere Minuten dauern. Die Logs zeigen danach `Realm 'soldat' imported` und
  `Keycloak ... started`.
- Für einen vollständig reproduzierbaren Neustart des Realm-Imports:

  ```powershell
  docker compose --env-file .env -f keycloak/compose.yml down -v
  docker compose --env-file .env -f keycloak/compose.yml up -d
  ```

- Bei `401` zuerst prüfen, ob der Token frisch ist und `iss`, `aud` sowie `azp`
  zu den Settings passen.
- Bei fehlendem Keycloak überspringen die tokenabhängigen pytest-Tests mit einer
  verständlichen Begründung; die Tests ohne Keycloak laufen weiterhin.

### Annahmen

- Keycloak läuft lokal unverschlüsselt auf Port 8080 im Dev-Modus; die Anwendung
  und die Testuser sind nicht für Produktion gedacht.
- Keycloak verwendet die eingebettete Dev-Datenbank und bleibt vollständig von der
  Soldat-PostgreSQL-Datenbank getrennt.

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

