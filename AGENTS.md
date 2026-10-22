# AGENTS.md – Projekt "Soldat" (FastAPI-Backend)

Diese Regeln gelten dauerhaft für das gesamte Repository. Ausdrückliche Anweisungen
im Chat haben Vorrang, außer sie würden die Sicherheitsregeln unten verletzen.

## Sprache

- Kommentare, Docstrings, README und Commit-Messages: **Deutsch**.
- Fachbegriffe der Domäne bleiben deutsch (wie in der DB), technische Begriffe englisch.

## Projektüberblick

REST-Backend mit **FastAPI** für Soldaten mit 1:1-Ausrüstung und 1:N-Verletzungen.
Datenbank: PostgreSQL 18 im Docker-Container (bereits vorhanden, TLS aktiv).
Security läuft über einen eigenen Keycloak-Docker-Container mit importiertem Realm.
Das Backend prüft JWTs per FastAPI-Dependency und erzwingt die Rollen `user` und
`admin` gemäß der Rollenmatrix der Aufgabe.

## Tech-Stack (verbindlich)

- Python, Paketverwaltung ausschließlich mit **uv** (`uv add`, `uv sync`, `uv run`).
  Kein pip, kein poetry.
- **FastAPI** mit Dependency Injection (`Depends`) für DB-Session, Repository/Service, Settings.
- **Pydantic v2**: getrennte Modelle für Create, Update und Response. Nie ORM-Objekte
  direkt zurückgeben.
- **SQLAlchemy 2.x async** (`AsyncSession`, `async_sessionmaker`, Driver `asyncpg`),
  deklarativ mit `Mapped`/`mapped_column`. SQLAlchemy mappt nur, kein `create_all`.
- **ruff** (Lint + Format) und **ty** (Typchecker), konfiguriert in `pyproject.toml`.
- **pytest** + `pytest-asyncio` + `httpx` (`ASGITransport`), Integrationstests gegen
  die echte PostgreSQL-DB.
- **Bruno**-Collection im Ordner `bruno/` als API-Client.
- Konfiguration über Umgebungsvariablen/`.env` (pydantic-settings), `.env.example` im Repo.
- Keycloak-Konfiguration liegt reproduzierbar unter `keycloak/`; die bestehende
  PostgreSQL-Konfiguration unter `extras/postgres/` bleibt unverändert.
- JWT-Prüfung nutzt ausschließlich RS256, überprüft Signatur, `exp`, `iss` und
  Audience beziehungsweise `azp`. JWKS werden asynchron geladen und gecacht.
- `GET`-Endpunkte benötigen `user` oder `admin`; `POST` und `PUT` benötigen `admin`.
  `/health` bleibt öffentlich.

## Prüfbefehle (vor JEDEM Commit alle ausführen, alle müssen grün sein)

```
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

- Neue Features müssen real getestet sein (Tests ausführen, nicht nur schreiben).
- Bei False Positives von ty (SQLAlchemy/Pydantic) gezielt und mit Kommentar
  ignorieren, den Check nie global abschalten.

## Git-Workflow

- "Commit early, commit often": kleine, inkrementelle Commits, ein Feature pro Commit.
- Conventional Commits auf Deutsch, z. B. `feat: GET /soldaten/{id} mit ETag`.
- Nur committen, wenn alle Prüfbefehle grün sind.
- Falls kein Repo existiert: `git init`.

## Sicherheitsregeln (nie verletzen)

- **Nie committen:** `server.key`, `server.crt`, `password.txt`, `.env`. Alle in die
  `.gitignore`, auch falls `postgres/` im Repo liegt.
- Keine Secrets im Code, nur über Settings/`.env`.
- Keycloak-Admin-Zugangsdaten kommen ausschließlich aus `.env`; die lokalen
  Testuser-Passwörter in der Realm-Datei sind ausdrücklich Dummy-Werte für die
  Entwicklung.
- Im Ordner `postgres/` nichts an der Docker-Konfiguration (`compose.yml` usw.) ändern.

## Datenbank

- Host `localhost`, Port `5432`, DB `soldat`, User `soldat`, Passwort `p`
  (nur lokale Entwicklung), Schema `soldat` (`search_path` ist für den User gesetzt).
- Der Server nutzt TLS mit selbst-signiertem Zertifikat. asyncpg per `ssl`/SSLContext
  verbinden; bei Self-Signed lokal ohne Hostname-/Zertifikatsprüfung, per Konfiguration
  steuerbar.
- **Relevante Dateien erkennst du am Inhalt:** `CREATE USER soldat ...` (DB-Skript),
  `CREATE SCHEMA IF NOT EXISTS AUTHORIZATION soldat` (Schema-Skript),
  `soldat.csv`, `ausruestung.csv`, `verletzung.csv`.
  **Alles mit "patient", "adresse", "rechnung" ignorieren**, unabhängig von
  Dateiname oder Suffix wie `_1`.
- Tabellen existieren noch nicht: per SQL-Skript anlegen (Schema `soldat`, Constraints,
  Indizes auf FK-Spalten, ON DELETE CASCADE) und CSVs wiederholbar importieren.
  Danach Sequences/Identity-Spalten hinter den höchsten ID-Wert setzen.

## Datenmodell

**soldat**: `id` (PK), `version` (int, Optimistic Locking), `vorname`, `nachname`,
`geburtsdatum` (date), `geschlecht` (MAENNLICH | WEIBLICH), `rang`
(REKRUT | SOLDAT | CAPTAIN), `username` (unique), `erzeugt`, `aktualisiert` (timestamp)

**ausruestung** (1:1): `id`, `waffe` (Klinge | Schrotflinte | ODM_GEAR),
`seriennummer` (unique, `AOT-` plus alphanumerisch), `soldat_id` (FK, unique)

**verletzung** (1:N): `id`, `verletzungsbezeichnung`, `behandelt` (bool),
`schweregrad` (LEICHT | MITTEL | SCHWER), `verletzungsdatum` (date), `soldat_id` (FK)

### CSV-Format

UTF-8 (Umlaute!), Trenner `;`, Kopfzeile, CRLF-Zeilenenden, letzte Zeile ohne
Zeilenumbruch, Timestamps ohne Zeitzone, feste IDs (1, 20, 30 ... 70).

## API-Regeln

- Basis-Pfad `/soldaten`, Responses nur als Pydantic-Modelle, einheitliches Fehlerformat
  (RFC 9457 Problem Details oder konsistentes JSON).
- **GET:** Pfad- und Query-Parameter. `GET /soldaten/{id}` liefert `ETag: "<version>"`;
  bei passendem `If-None-Match` **304** ohne Body. Eager Loading, kein N+1.
- **POST:** Validierung per Pydantic, 201 mit `Location`-Header, Soldat + Ausrüstung
  (+ optional Verletzungen) in einer Transaktion. Doppelter `username` oder
  `seriennummer` → 409, Validierungsfehler → 422.
- **PUT:** Lost-Update-Schutz über `If-Match` mit der Version:
  fehlt → **428**, veraltet → **412**, Erfolg → neuer `ETag` (Version + 1).
  Prüfen und Hochzählen atomar (`UPDATE ... WHERE id AND version` bzw.
  `StaleDataError` auf 412 abbilden). Jede Änderung am Soldaten oder an seiner
  Ausrüstung erhöht die `version` des Soldaten genau um 1.
- **Validierung muss zu den Seed-Daten passen:** `username` erlaubt Punkte
  (z. B. `clara.f`), alle CSV-Datensätze müssen die Validierung bestehen.

## Code-Qualität

- Vollständige Typannotationen, keine blockierenden DB-Aufrufe (überall `async`/`await`).
- Tests sind unabhängig voneinander und hinterlassen keine Daten in der DB.
- Projektstruktur: `src/soldat/` (`main.py`, `config.py`, `db.py`, `models.py`,
  `schemas.py`, `repository.py`, `service.py`, `routers/`), `tests/`, `scripts/`, `bruno/`.
- Bei Unklarheiten: sinnvolle Annahme treffen, im README unter "Annahmen"
  dokumentieren und weitermachen. Nur bei echten Blockern anhalten und nachfragen.
