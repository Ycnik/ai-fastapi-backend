"""Datenbankzugriff für Soldaten."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from .models import Ausruestung, Geschlecht, Rang, Schweregrad, Soldat, Verletzung, Waffe


class SoldatRepository:
    """Kapselt alle SQLAlchemy-Abfragen der Soldaten-Ressource."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _with_relations(query: Select[Any]) -> Select[Any]:
        return query.options(joinedload(Soldat.ausruestung), selectinload(Soldat.verletzungen))

    async def get(self, soldat_id: int) -> Soldat | None:
        query = self._with_relations(select(Soldat).where(Soldat.id == soldat_id))
        return await self.session.scalar(query)

    async def list(
        self,
        *,
        nachname: str | None,
        rang: Rang | None,
        geschlecht: Geschlecht | None,
        waffe: Waffe | None,
        schweregrad: Schweregrad | None,
        limit: int,
        offset: int,
    ) -> Sequence[Soldat]:
        query = select(Soldat).distinct().join(Soldat.ausruestung, isouter=waffe is not None)
        if schweregrad is not None:
            query = query.join(Soldat.verletzungen)
        if nachname:
            query = query.where(Soldat.nachname.ilike(f"%{nachname}%"))
        if rang is not None:
            query = query.where(Soldat.rang == rang)
        if geschlecht is not None:
            query = query.where(Soldat.geschlecht == geschlecht)
        if waffe is not None:
            query = query.where(Ausruestung.waffe == waffe)
        if schweregrad is not None:
            query = query.where(Verletzung.schweregrad == schweregrad)
        query = self._with_relations(query.order_by(Soldat.id).limit(limit).offset(offset))
        return (await self.session.scalars(query)).unique().all()

    async def injuries(self, soldat_id: int) -> Sequence[Verletzung]:
        query = select(Verletzung).where(Verletzung.soldat_id == soldat_id).order_by(Verletzung.id)
        return (await self.session.scalars(query)).all()
