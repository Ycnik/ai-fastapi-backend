"""REST-Endpunkte der Soldatenverwaltung."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

from ..db import get_session
from ..models import Geschlecht, Rang, Schweregrad, Waffe
from ..schemas import SoldatCreate, SoldatResponse, SoldatUpdate, VerletzungResponse
from ..service import (
    DuplicateResourceError,
    SoldatNotFoundError,
    SoldatService,
    VersionConflictError,
)

router = APIRouter(prefix="/soldaten", tags=["Soldaten"])


def get_service(session=Depends(get_session)) -> SoldatService:  # noqa: B008
    """DI-Hook für Service und spätere Security-Dependencies."""
    return SoldatService(session)


def _parse_etag(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        stripped = stripped[1:-1]
    try:
        return int(stripped)
    except ValueError:
        return None


@router.get("/{soldat_id}", response_model=SoldatResponse)
async def get_soldat(
    soldat_id: int,
    response: Response,
    if_none_match: Annotated[str | None, Header()] = None,
    service: SoldatService = Depends(get_service),  # noqa: B008
) -> SoldatResponse | Response:
    soldat = await service.get(soldat_id)
    if soldat is None:
        raise HTTPException(status_code=404, detail="Soldat nicht gefunden")
    etag = f'"{soldat.version}"'
    response.headers["ETag"] = etag
    if _parse_etag(if_none_match) == soldat.version:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    return SoldatResponse.model_validate(soldat)


@router.get("", response_model=list[SoldatResponse])
async def list_soldaten(
    nachname: str | None = None,
    rang: Rang | None = None,
    geschlecht: Geschlecht | None = None,
    waffe: Waffe | None = None,
    schweregrad: Schweregrad | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    service: SoldatService = Depends(get_service),  # noqa: B008
) -> list[SoldatResponse]:
    soldaten = await service.list(
        nachname=nachname,
        rang=rang,
        geschlecht=geschlecht,
        waffe=waffe,
        schweregrad=schweregrad,
        limit=limit,
        offset=offset,
    )
    return [SoldatResponse.model_validate(item) for item in soldaten]


@router.get("/{soldat_id}/verletzungen", response_model=list[VerletzungResponse])
async def list_verletzungen(
    soldat_id: int,
    service: SoldatService = Depends(get_service),  # noqa: B008
) -> list[VerletzungResponse]:
    if await service.get(soldat_id) is None:
        raise HTTPException(status_code=404, detail="Soldat nicht gefunden")
    return [VerletzungResponse.model_validate(item) for item in await service.injuries(soldat_id)]


@router.post("", response_model=SoldatResponse, status_code=201)
async def create_soldat(
    payload: SoldatCreate,
    response: Response,
    service: SoldatService = Depends(get_service),  # noqa: B008
) -> SoldatResponse:
    try:
        soldat = await service.create(payload)
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    response.headers["Location"] = f"/soldaten/{soldat.id}"
    response.headers["ETag"] = f'"{soldat.version}"'
    return SoldatResponse.model_validate(soldat)


@router.put("/{soldat_id}", status_code=204)
async def update_soldat(
    soldat_id: int,
    payload: SoldatUpdate,
    if_match: Annotated[str | None, Header()] = None,
    service: SoldatService = Depends(get_service),  # noqa: B008
) -> Response:
    expected_version = _parse_etag(if_match)
    if if_match is None:
        raise HTTPException(status_code=428, detail="If-Match ist erforderlich")
    if expected_version is None:
        raise HTTPException(status_code=412, detail="Ungültige If-Match-Version")
    try:
        new_version = await service.update(soldat_id, expected_version, payload)
    except SoldatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VersionConflictError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"ETag": f'"{new_version}"'})
