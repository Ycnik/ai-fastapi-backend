"""FastAPI-Anwendung."""

from fastapi import FastAPI

from .config import get_settings
from .routers.soldat import router as soldat_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(soldat_router)


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    """Liveness-Endpunkt ohne Datenbankzugriff."""
    return {"status": "ok"}
