from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

from .jwks import JwksFetcher
from .settings import AuthSettings

bearer = HTTPBearer()


@lru_cache
def _settings() -> AuthSettings:
    return AuthSettings()


@lru_cache
def _fetcher() -> JwksFetcher:
    s = _settings()
    return JwksFetcher(s.keycloak_jwks_url, s.jwks_cache_ttl)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    token = creds.credentials
    try:
        header = jwt.get_unverified_header(token)
        print(header)
        key = _fetcher().find_key(header["kid"])
        s = _settings()
        return jwt.decode(
            token,
            key,
            algorithms=[header["alg"]],
            audience=s.keycloak_audience,
            issuer=s.keycloak_issuer,
        )
    except jwt.JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")
