"""SQLAlchemy-Modelle im deklarativen 2.0-Stil."""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Basisklasse für die ORM-Modelle."""


class Geschlecht(StrEnum):
    MAENNLICH = "MAENNLICH"
    WEIBLICH = "WEIBLICH"


class Rang(StrEnum):
    REKRUT = "REKRUT"
    SOLDAT = "SOLDAT"
    CAPTAIN = "CAPTAIN"


class Waffe(StrEnum):
    KLINGE = "Klinge"
    SCHROTFLINTE = "Schrotflinte"
    ODM_GEAR = "ODM_GEAR"


class Schweregrad(StrEnum):
    LEICHT = "LEICHT"
    MITTEL = "MITTEL"
    SCHWER = "SCHWER"


def enum_values(enum_type: type[StrEnum]) -> list[str]:
    """Gibt die fachlichen Enum-Werte für PostgreSQL zurück."""
    return [item.value for item in enum_type]


GESCHLECHT_DB = SAEnum(
    Geschlecht,
    name="geschlecht",
    schema="soldat",
    native_enum=True,
    create_type=False,
    values_callable=enum_values,
)
RANG_DB = SAEnum(
    Rang,
    name="rang",
    schema="soldat",
    native_enum=True,
    create_type=False,
    values_callable=enum_values,
)
WAFFE_DB = SAEnum(
    Waffe,
    name="waffe",
    schema="soldat",
    native_enum=True,
    create_type=False,
    values_callable=enum_values,
)
SCHWEREGRAD_DB = SAEnum(
    Schweregrad,
    name="schweregrad",
    schema="soldat",
    native_enum=True,
    create_type=False,
    values_callable=enum_values,
)


class Soldat(Base):
    """Stammdaten eines Soldaten."""

    __tablename__ = "soldat"
    __table_args__ = {"schema": "soldat"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vorname: Mapped[str] = mapped_column(String(80), nullable=False)
    nachname: Mapped[str] = mapped_column(String(80), nullable=False)
    geburtsdatum: Mapped[date] = mapped_column(Date, nullable=False)
    geschlecht: Mapped[Geschlecht] = mapped_column(GESCHLECHT_DB, nullable=False)
    rang: Mapped[Rang] = mapped_column(RANG_DB, nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    erzeugt: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=datetime.now, server_default=func.now()
    )
    aktualisiert: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
        onupdate=datetime.now,
    )

    ausruestung: Mapped["Ausruestung"] = relationship(
        back_populates="soldat", cascade="all, delete-orphan", uselist=False
    )
    verletzungen: Mapped[list["Verletzung"]] = relationship(
        back_populates="soldat", cascade="all, delete-orphan"
    )


class Ausruestung(Base):
    """1:1-Ausrüstung eines Soldaten."""

    __tablename__ = "ausruestung"
    __table_args__ = {"schema": "soldat"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    waffe: Mapped[Waffe] = mapped_column(WAFFE_DB, nullable=False)
    seriennummer: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    soldat_id: Mapped[int] = mapped_column(
        ForeignKey("soldat.soldat.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    soldat: Mapped[Soldat] = relationship(back_populates="ausruestung")


class Verletzung(Base):
    """1:N-Verletzung eines Soldaten."""

    __tablename__ = "verletzung"
    __table_args__ = {"schema": "soldat"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    verletzungsbezeichnung: Mapped[str] = mapped_column(String(200), nullable=False)
    behandelt: Mapped[bool] = mapped_column(Boolean, nullable=False)
    schweregrad: Mapped[Schweregrad] = mapped_column(SCHWEREGRAD_DB, nullable=False)
    verletzungsdatum: Mapped[date] = mapped_column(Date, nullable=False)
    soldat_id: Mapped[int] = mapped_column(
        ForeignKey("soldat.soldat.id", ondelete="CASCADE"), nullable=False
    )
    soldat: Mapped[Soldat] = relationship(back_populates="verletzungen")
