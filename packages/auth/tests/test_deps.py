import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from tests.conftest import make_token, ISSUER, AUDIENCE


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture
def patched_jwks(mocker, keypair_a):
    jwks = {"keys": [keypair_a["jwk"]]}
    return mocker.patch("cf_auth.jwks.httpx.get", return_value=_Resp(jwks))


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_valid_token_returns_claims(
    auth_env, reset_deps_caches, patched_jwks, keypair_a
):
    from cf_auth.deps import get_current_user

    token = make_token(keypair_a["pem"], keypair_a["kid"], claims={"sub": "alice"})
    claims = get_current_user(_creds(token))

    assert claims["sub"] == "alice"
    assert claims["iss"] == ISSUER
    assert claims["aud"] == AUDIENCE


def test_wrong_audience_raises_401(
    auth_env, reset_deps_caches, patched_jwks, keypair_a
):
    from cf_auth.deps import get_current_user

    token = make_token(keypair_a["pem"], keypair_a["kid"], claims={"aud": "other"})
    with pytest.raises(HTTPException) as ei:
        get_current_user(_creds(token))
    assert ei.value.status_code == 401


def test_wrong_issuer_raises_401(
    auth_env, reset_deps_caches, patched_jwks, keypair_a
):
    from cf_auth.deps import get_current_user

    token = make_token(keypair_a["pem"], keypair_a["kid"], claims={"iss": "evil"})
    with pytest.raises(HTTPException) as ei:
        get_current_user(_creds(token))
    assert ei.value.status_code == 401


def test_signature_from_unknown_key_raises_401(
    auth_env, reset_deps_caches, patched_jwks, keypair_a, keypair_b
):
    """Token signed by keypair_b but JWKS only contains keypair_a → unknown kid."""
    from cf_auth.deps import get_current_user

    token = make_token(keypair_b["pem"], keypair_b["kid"])
    with pytest.raises(HTTPException) as ei:
        get_current_user(_creds(token))
    assert ei.value.status_code == 401


def test_malformed_token_raises_401(auth_env, reset_deps_caches, patched_jwks):
    from cf_auth.deps import get_current_user

    with pytest.raises(HTTPException) as ei:
        get_current_user(_creds("not-a-jwt"))
    assert ei.value.status_code == 401


def test_settings_loaded_from_env(auth_env, reset_deps_caches):
    from cf_auth.deps import _settings

    s = _settings()
    assert s.keycloak_issuer == ISSUER
    assert s.keycloak_audience == AUDIENCE
    assert s.jwks_cache_ttl == 600
