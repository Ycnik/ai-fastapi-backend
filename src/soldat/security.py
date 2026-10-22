"""Asynchrone JWT-Prüfung gegen die Keycloak-JWKS."""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import RSAAlgorithm
from pydantic import BaseModel, Field

from .config import Settings, get_settings


class TokenValidationError(Exception):
    """Ein Bearer-Token konnte nicht sicher validiert werden."""


class CurrentUser(BaseModel):
    """Die für die API relevanten Claims eines validierten Tokens."""

    subject: str
    username: str
    roles: set[str] = Field(default_factory=set)


@dataclass
class _JwksCache:
    """Gecachte JWKS-Schlüssel mit Ablaufzeit."""

    keys: dict[str, Any]
    expires_at: float


class JwksClient:
    """Lädt Keycloak-Schlüssel asynchron und cached sie für mehrere Requests."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: _JwksCache | None = None
        self._lock = asyncio.Lock()

    async def _load_keys(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
            response = await client.get(self._settings.keycloak_jwks_url)
            response.raise_for_status()
        data = response.json()
        keys = data.get("keys")
        if not isinstance(keys, list):
            raise TokenValidationError("Keycloak-JWKS enthalten keine Schlüssel")
        return {
            item["kid"]: RSAAlgorithm.from_jwk(json.dumps(item))
            for item in keys
            if isinstance(item, dict)
            and item.get("kid")
            and item.get("kty") == "RSA"
            and item.get("alg") == "RS256"
        }

    async def get_key(self, key_id: str) -> Any:
        now = time.monotonic()
        if self._cache is not None and self._cache.expires_at > now:
            key = self._cache.keys.get(key_id)
            if key is not None:
                return key

        async with self._lock:
            now = time.monotonic()
            if self._cache is not None and self._cache.expires_at > now:
                key = self._cache.keys.get(key_id)
                if key is not None:
                    return key
            try:
                keys = await self._load_keys()
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise TokenValidationError("Keycloak-JWKS konnten nicht geladen werden") from exc
            self._cache = _JwksCache(
                keys=keys,
                expires_at=time.monotonic() + self._settings.keycloak_jwks_cache_seconds,
            )
            key = keys.get(key_id)
            if key is None:
                raise TokenValidationError("Signaturschlüssel des Tokens ist unbekannt")
            return key


_bearer_scheme = HTTPBearer(auto_error=False)


def get_jwks_client(settings: Settings = Depends(get_settings)) -> JwksClient:  # noqa: B008
    """Stellt den gecachten JWKS-Client per FastAPI-DI bereit."""
    return _jwks_client_for_settings(settings)


_jwks_clients: dict[int, JwksClient] = {}


def _jwks_client_for_settings(settings: Settings) -> JwksClient:
    """Liefert pro Settings-Instanz einen wiederverwendbaren JWKS-Client."""
    cache_key = id(settings)
    client = _jwks_clients.get(cache_key)
    if client is None:
        client = JwksClient(settings)
        _jwks_clients[cache_key] = client
    return client


async def validate_token(token: str, settings: Settings, jwks: JwksClient) -> CurrentUser:
    """Validiert Signatur, Algorithmus, Ablauf, Issuer, Audience und Realm-Rollen."""
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise TokenValidationError("Nur RS256-Tokens mit kid werden akzeptiert")
        key = await jwks.get_key(header["kid"])
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            issuer=settings.keycloak_issuer_url,
            options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
        )
    except TokenValidationError:
        raise
    except (jwt.PyJWTError, TypeError, ValueError) as exc:
        raise TokenValidationError("Bearer-Token ist ungültig") from exc

    audience = claims.get("aud", [])
    audiences = audience if isinstance(audience, list) else [audience]
    authorized_client = claims.get("azp") == settings.keycloak_client_id
    if settings.keycloak_audience not in audiences and not authorized_client:
        raise TokenValidationError("Token-Audience passt nicht zur API")

    realm_access = claims.get("realm_access", {})
    raw_roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
    roles = {role for role in raw_roles if isinstance(role, str)}
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenValidationError("Token enthält keinen gültigen subject-Claim")
    username = claims.get("preferred_username", subject)
    if not isinstance(username, str) or not username:
        username = subject
    return CurrentUser(subject=subject, username=username, roles=roles)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
    jwks: JwksClient = Depends(get_jwks_client),  # noqa: B008
) -> CurrentUser:
    """Liefert den validierten Benutzer oder antwortet mit HTTP 401."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentifizierung erforderlich",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        return await validate_token(credentials.credentials, settings, jwks)
    except TokenValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_roles(*required_roles: str):
    """Erzeugt eine Dependency, die mindestens eine angegebene Rolle verlangt."""

    async def dependency(
        current_user: CurrentUser = Depends(get_current_user),  # noqa: B008
    ) -> CurrentUser:
        if not current_user.roles.intersection(required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unzureichende Berechtigung",
            )
        return current_user

    return dependency
