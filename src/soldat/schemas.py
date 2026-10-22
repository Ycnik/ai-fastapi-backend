"""Pydantic-Modelle für Requests und Responses."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from .models import Geschlecht, Rang, Schweregrad, Waffe

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Username = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z][a-zA-Z0-9._-]{2,49}$")]
Seriennummer = Annotated[str, StringConstraints(pattern=r"^AOT-[A-Za-z0-9]+$")]


class AusruestungBase(BaseModel):
    """Gemeinsame Felder der Ausrüstung."""

    waffe: Waffe
    seriennummer: Seriennummer


class AusruestungResponse(AusruestungBase):
    """Ausrüstung in einer API-Antwort."""

    model_config = ConfigDict(from_attributes=True)
    id: int


class VerletzungBase(BaseModel):
    """Gemeinsame Felder einer Verletzung."""

    verletzungsbezeichnung: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    behandelt: bool
    schweregrad: Schweregrad
    verletzungsdatum: date

    @field_validator("verletzungsdatum")
    @classmethod
    def datum_nicht_in_der_zukunft(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Das Verletzungsdatum darf nicht in der Zukunft liegen")
        return value


class VerletzungCreate(VerletzungBase):
    """Verletzung beim Anlegen eines Soldaten."""


class VerletzungResponse(VerletzungBase):
    """Verletzung in einer API-Antwort."""

    model_config = ConfigDict(from_attributes=True)
    id: int


class SoldatFields(BaseModel):
    """Stammdaten ohne technische Response-Felder."""

    vorname: Name
    nachname: Name
    geburtsdatum: date
    geschlecht: Geschlecht
    rang: Rang
    username: Username

    @field_validator("geburtsdatum")
    @classmethod
    def geburtsdatum_in_der_vergangenheit(cls, value: date) -> date:
        if value >= date.today():
            raise ValueError("Das Geburtsdatum muss in der Vergangenheit liegen")
        return value


class SoldatCreate(SoldatFields):
    """Request zum Anlegen eines Soldaten."""

    ausruestung: AusruestungBase
    verletzungen: list[VerletzungCreate] = Field(default_factory=list)


class SoldatUpdate(SoldatFields):
    """Request zum Aktualisieren eines Soldaten."""

    ausruestung: AusruestungBase


class SoldatResponse(SoldatFields):
    """Vollständige Soldatenantwort."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    version: int
    erzeugt: datetime
    aktualisiert: datetime
    ausruestung: AusruestungResponse
    verletzungen: list[VerletzungResponse]
