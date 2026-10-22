"""Prüft, dass alle mitgelieferten CSV-Daten die Request-Validierung bestehen."""

import csv
from pathlib import Path

from soldat.schemas import SoldatCreate

CSV_DIR = Path(__file__).parents[1] / "extras" / "postgres" / "init" / "soldat" / "csv"


def read_csv(name: str) -> list[dict[str, str]]:
    with (CSV_DIR / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=";"))


def test_seed_daten_bestehen_request_validierung() -> None:
    equipment = {row["soldat_id"]: row for row in read_csv("ausruestung.csv")}
    injuries: dict[str, list[dict[str, str]]] = {}
    for row in read_csv("verletzung.csv"):
        injuries.setdefault(row["soldat_id"], []).append(row)

    for row in read_csv("soldat.csv"):
        equipment_row = equipment[row["id"]]
        SoldatCreate.model_validate(
            {
                **row,
                "ausruestung": {
                    "waffe": equipment_row["waffe"],
                    "seriennummer": equipment_row["seriennummer"],
                },
                "verletzungen": [
                    {
                        **injury,
                        "behandelt": injury["behandelt"].lower() == "true",
                    }
                    for injury in injuries.get(row["id"], [])
                ],
            }
        )
