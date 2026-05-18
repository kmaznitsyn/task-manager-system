import pytest
from fastapi import HTTPException

from cf_auth.jwks import JwksFetcher


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_caches_jwks(mocker, keypair_a):
    jwks = {"keys": [keypair_a["jwk"]]}
    get = mocker.patch("cf_auth.jwks.httpx.get", return_value=_Resp(jwks))

    f = JwksFetcher("https://x/jwks", ttl=600)
    assert f.find_key("kid-a") == keypair_a["jwk"]
    assert f.find_key("kid-a") == keypair_a["jwk"]

    assert get.call_count == 1


def test_unknown_kid_busts_cache_and_retries(mocker, keypair_a, keypair_b):
    first = {"keys": [keypair_a["jwk"]]}
    second = {"keys": [keypair_a["jwk"], keypair_b["jwk"]]}
    get = mocker.patch(
        "cf_auth.jwks.httpx.get",
        side_effect=[_Resp(first), _Resp(second)],
    )

    f = JwksFetcher("https://x/jwks", ttl=600)
    assert f.find_key("kid-a") == keypair_a["jwk"]  # warm cache
    # kid-b not in first JWKS → must refetch and find it
    assert f.find_key("kid-b") == keypair_b["jwk"]

    assert get.call_count == 2


def test_kid_still_missing_after_refresh_raises_401(mocker, keypair_a):
    jwks = {"keys": [keypair_a["jwk"]]}
    mocker.patch("cf_auth.jwks.httpx.get", return_value=_Resp(jwks))

    f = JwksFetcher("https://x/jwks", ttl=600)
    with pytest.raises(HTTPException) as ei:
        f.find_key("nope")
    assert ei.value.status_code == 401


def test_http_error_propagates(mocker):
    class BadResp:
        def raise_for_status(self):
            raise RuntimeError("boom")

        def json(self):  # pragma: no cover
            return {}

    mocker.patch("cf_auth.jwks.httpx.get", return_value=BadResp())

    f = JwksFetcher("https://x/jwks", ttl=600)
    with pytest.raises(RuntimeError):
        f.find_key("anything")
