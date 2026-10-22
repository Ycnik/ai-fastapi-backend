"""Fachlogik und Transaktionsgrenzen der Soldaten-Ressource."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Ausruestung, Rang, Soldat, Verletzung
from .repository import SoldatRepository
from .schemas import SoldatCreate, SoldatUpdate


class DuplicateResourceError(Exception):
    """Ein eindeutiger Datenbankwert ist bereits vorhanden."""


class SoldatNotFoundError(Exception):
    """Der angeforderte Soldat ist nicht vorhanden."""


class VersionConflictError(Exception):
    """Die übermittelte Optimistic-Locking-Version ist veraltet."""


class SoldatService:
    """Fachlogik mit atomarem Update über die Versionsspalte."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SoldatRepository(session)

    async def get(self, soldat_id: int) -> Soldat | None:
        return await self.repository.get(soldat_id)

    async def list(
        self,
        *,
        nachname: str | None,
        rang: Rang | None,
        geschlecht: object | None,
        waffe: object | None,
        schweregrad: object | None,
        limit: int,
        offset: int,
    ) -> Sequence[Soldat]:
        from .models import Geschlecht, Schweregrad, Waffe

        return await self.repository.list(
            nachname=nachname,
            rang=rang,
            geschlecht=geschlecht if isinstance(geschlecht, Geschlecht) else None,
            waffe=waffe if isinstance(waffe, Waffe) else None,
            schweregrad=schweregrad if isinstance(schweregrad, Schweregrad) else None,
            limit=limit,
            offset=offset,
        )

    async def injuries(self, soldat_id: int) -> Sequence[Verletzung]:
        return await self.repository.injuries(soldat_id)

    async def create(self, payload: SoldatCreate) -> Soldat:
        if await self.session.scalar(select(Soldat.id).where(Soldat.username == payload.username)):
            raise DuplicateResourceError("Username oder Seriennummer ist bereits vorhanden")
        if await self.session.scalar(
            select(Ausruestung.id).where(
                Ausruestung.seriennummer == payload.ausruestung.seriennummer
            )
        ):
            raise DuplicateResourceError("Username oder Seriennummer ist bereits vorhanden")
        soldat = Soldat(
            vorname=payload.vorname,
            nachname=payload.nachname,
            geburtsdatum=payload.geburtsdatum,
            geschlecht=payload.geschlecht,
            rang=payload.rang,
            username=payload.username,
            ausruestung=Ausruestung(**payload.ausruestung.model_dump()),
            verletzungen=[Verletzung(**item.model_dump()) for item in payload.verletzungen],
        )
        self.session.add(soldat)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateResourceError(
                "Username oder Seriennummer ist bereits vorhanden"
            ) from exc
        result = await self.repository.get(soldat.id)
        if result is None:
            raise SoldatNotFoundError("Der neu angelegte Soldat konnte nicht gelesen werden")
        return result

    async def update(self, soldat_id: int, expected_version: int, payload: SoldatUpdate) -> int:
        current_version = await self.session.scalar(
            select(Soldat.version).where(Soldat.id == soldat_id)
        )
        if current_version is None:
            raise SoldatNotFoundError("Soldat nicht gefunden")
        if current_version != expected_version:
            raise VersionConflictError("Die Version ist veraltet")
        if await self.session.scalar(
            select(Soldat.id).where(
                Soldat.username == payload.username,
                Soldat.id != soldat_id,
            )
        ):
            raise DuplicateResourceError("Username oder Seriennummer ist bereits vorhanden")
        if await self.session.scalar(
            select(Ausruestung.id).where(
                Ausruestung.seriennummer == payload.ausruestung.seriennummer,
                Ausruestung.soldat_id != soldat_id,
            )
        ):
            raise DuplicateResourceError("Username oder Seriennummer ist bereits vorhanden")
        result = await self.session.execute(
            update(Soldat)
            .where(Soldat.id == soldat_id, Soldat.version == expected_version)
            .values(
                vorname=payload.vorname,
                nachname=payload.nachname,
                geburtsdatum=payload.geburtsdatum,
                geschlecht=payload.geschlecht,
                rang=payload.rang,
                username=payload.username,
                version=Soldat.version + 1,
                aktualisiert=datetime.now(),
            )
        )
        if getattr(result, "rowcount", 0) == 0:
            await self.session.rollback()
            if await self.repository.get(soldat_id) is None:
                raise SoldatNotFoundError("Soldat nicht gefunden")
            raise VersionConflictError("Die Version ist veraltet")
        equipment_result = await self.session.execute(
            update(Ausruestung)
            .where(Ausruestung.soldat_id == soldat_id)
            .values(**payload.ausruestung.model_dump())
        )
        if getattr(equipment_result, "rowcount", 0) == 0:
            await self.session.rollback()
            raise SoldatNotFoundError("Ausrüstung nicht gefunden")
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateResourceError(
                "Username oder Seriennummer ist bereits vorhanden"
            ) from exc
        return expected_version + 1
