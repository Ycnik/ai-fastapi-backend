"""Unit-nahe Tests für die Keycloak-JWT-Prüfung."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from soldat.config import Settings
from soldat.security import JwksClient, TokenValidationError, validate_token


class StaticJwksClient(JwksClient):
    """Stellt im Test einen festen RSA-Schlüssel ohne Netzwerkzugriff bereit."""

    def __init__(self, key: RSAPublicKey) -> None:
        self.key = key

    async def get_key(self, key_id: str) -> RSAPublicKey:
        return self.key


@pytest.fixture
def signing_keys() -> tuple[RSAPrivateKey, RSAPublicKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def make_token(private_key: RSAPrivateKey, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": "subject-1",
        "preferred_username": "admin",
        "iss": "http://localhost:8080/realms/soldat",
        "aud": "soldat-api",
        "azp": "soldat-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "realm_access": {"roles": ["admin"]},
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


@pytest.fixture
def settings() -> Settings:
    return Settings(
        keycloak_issuer_url="http://localhost:8080/realms/soldat",
        keycloak_audience="soldat-api",
        keycloak_client_id="soldat-api",
    )


@pytest.mark.asyncio
async def test_gueltiges_token_liefert_current_user(
    signing_keys: tuple[RSAPrivateKey, RSAPublicKey], settings: Settings
) -> None:
    private_key, public_key = signing_keys
    user = await validate_token(make_token(private_key), settings, StaticJwksClient(public_key))
    assert user.username == "admin"
    assert user.roles == {"admin"}


@pytest.mark.asyncio
async def test_abgelaufenes_token_wird_abgelehnt(
    signing_keys: tuple[RSAPrivateKey, RSAPublicKey], settings: Settings
) -> None:
    private_key, public_key = signing_keys
    token = make_token(private_key, exp=int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()))
    with pytest.raises(TokenValidationError):
        await validate_token(token, settings, StaticJwksClient(public_key))


@pytest.mark.asyncio
async def test_falscher_issuer_wird_abgelehnt(
    signing_keys: tuple[RSAPrivateKey, RSAPublicKey], settings: Settings
) -> None:
    private_key, public_key = signing_keys
    token = make_token(private_key, iss="http://evil.example/realms/soldat")
    with pytest.raises(TokenValidationError):
        await validate_token(token, settings, StaticJwksClient(public_key))


@pytest.mark.asyncio
async def test_manipulierte_signatur_wird_abgelehnt(
    signing_keys: tuple[RSAPrivateKey, RSAPublicKey], settings: Settings
) -> None:
    private_key, public_key = signing_keys
    token = make_token(private_key)
    manipulated = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(TokenValidationError):
        await validate_token(manipulated, settings, StaticJwksClient(public_key))
