"""Konfiguration aus Umgebungsvariablen und optionaler .env-Datei."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Laufzeitkonfiguration der Anwendung."""

    app_name: str = "Soldat-Backend"
    database_url: str = "postgresql+asyncpg://soldat:p@localhost:5432/soldat"
    db_ssl: bool = True
    db_ssl_verify: bool = False
    db_ssl_cert: str | None = "extras/postgres/init/tls/server.crt"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    @property
    def db_ssl_cert_path(self) -> Path | None:
        """Liefert den Zertifikatspfad, sofern einer konfiguriert ist."""
        if self.db_ssl_cert is None:
            return None
        return Path(self.db_ssl_cert)


@lru_cache
def get_settings() -> Settings:
    """Liefert eine gecachte Settings-Instanz für FastAPI-Dependencies."""
    return Settings()
