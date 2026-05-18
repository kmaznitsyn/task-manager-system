import httpx
from cachetools import TTLCache
from fastapi import HTTPException, status


class JwksFetcher:
    def __init__(self, jwks_url: str, ttl: int = 600):
        self.jwks_url = jwks_url
        self._cache: TTLCache = TTLCache(maxsize=1, ttl=ttl)

    def _fetch(self) -> dict:
        if "jwks" in self._cache:
            return self._cache["jwks"]
        resp = httpx.get(self.jwks_url, timeout=5.0)
        resp.raise_for_status()
        self._cache["jwks"] = resp.json()
        return self._cache["jwks"]

    def find_key(self, kid: str) -> dict:
        jwks = self._fetch()
        for key in jwks["keys"]:
            if key["kid"] == kid:
                return key
        # rotation — bust cache and try once more
        self._cache.clear()
        jwks = self._fetch()
        for key in jwks["keys"]:
            if key["kid"] == kid:
                return key
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown signing key")
