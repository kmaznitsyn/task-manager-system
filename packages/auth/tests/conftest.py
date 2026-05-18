import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk
from jose.utils import long_to_base64

ISSUER = "https://test-issuer.example/realms/test"
AUDIENCE = "test-aud"
JWKS_URL = "https://test-issuer.example/realms/test/protocol/openid-connect/certs"


def _rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_numbers = key.public_key().public_numbers()
    return pem.decode(), pub_numbers


def _jwk_entry(kid: str, pub_numbers) -> dict:
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": long_to_base64(pub_numbers.n).decode(),
        "e": long_to_base64(pub_numbers.e).decode(),
    }


@pytest.fixture
def keypair_a():
    pem, pub = _rsa_keypair()
    return {"kid": "kid-a", "pem": pem, "jwk": _jwk_entry("kid-a", pub)}


@pytest.fixture
def keypair_b():
    pem, pub = _rsa_keypair()
    return {"kid": "kid-b", "pem": pem, "jwk": _jwk_entry("kid-b", pub)}


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ISSUER", ISSUER)
    monkeypatch.setenv("KEYCLOAK_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("KEYCLOAK_JWKS_URL", JWKS_URL)
    monkeypatch.setenv("JWKS_CACHE_TTL", "600")


@pytest.fixture
def reset_deps_caches():
    from cf_auth import deps

    deps._settings.cache_clear()
    deps._fetcher.cache_clear()
    yield
    deps._settings.cache_clear()
    deps._fetcher.cache_clear()


def make_token(pem: str, kid: str, *, claims: dict | None = None) -> str:
    from jose import jwt

    payload = {"sub": "user-1", "iss": ISSUER, "aud": AUDIENCE}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, pem, algorithm="RS256", headers={"kid": kid})
