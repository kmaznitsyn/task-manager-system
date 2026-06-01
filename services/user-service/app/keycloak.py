"""Keycloak Admin REST client.

user-service talks to Keycloak with its own confidential client
(service account, grant_type=client_credentials) that holds the
realm-management roles ``view-users`` and ``manage-users``. The access token
is cached until shortly before it expires and reused across requests, so a
burst of admin calls does not hammer the token endpoint.
"""
import threading
import time

import httpx

from app.config import settings


class KeycloakError(RuntimeError):
    """Raised when the Keycloak Admin API returns an unexpected response."""


_token: str | None = None
_token_expiry: float = 0.0
_lock = threading.Lock()


def _token_url() -> str:
    return (
        f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/token"
    )


def _admin_base() -> str:
    return f"{settings.keycloak_server_url}/admin/realms/{settings.keycloak_realm}"


def _get_token() -> str:
    global _token, _token_expiry
    with _lock:
        if _token and time.monotonic() < _token_expiry:
            return _token
        resp = httpx.post(
            _token_url(),
            data={
                "grant_type": "client_credentials",
                "client_id": settings.keycloak_admin_client_id,
                "client_secret": settings.keycloak_admin_client_secret,
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise KeycloakError(f"token request failed ({resp.status_code})")
        body = resp.json()
        _token = body["access_token"]
        # refresh 30s before the real expiry to avoid using a token mid-flight
        _token_expiry = time.monotonic() + body.get("expires_in", 60) - 30
        return _token


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_token()}"}


def list_users(first: int, max_results: int, search: str | None) -> list[dict]:
    params: dict[str, str | int] = {"first": first, "max": max_results}
    if search:
        params["search"] = search
    resp = httpx.get(
        f"{_admin_base()}/users",
        params=params,
        headers=_auth_headers(),
        timeout=10.0,
    )
    if resp.status_code != 200:
        raise KeycloakError(f"list users failed ({resp.status_code})")
    return resp.json()


def count_users(search: str | None) -> int:
    params: dict[str, str] = {}
    if search:
        params["search"] = search
    resp = httpx.get(
        f"{_admin_base()}/users/count",
        params=params,
        headers=_auth_headers(),
        timeout=10.0,
    )
    if resp.status_code != 200:
        raise KeycloakError(f"count users failed ({resp.status_code})")
    return resp.json()


def delete_user(user_id: str) -> None:
    """Delete a user. Idempotent: a 404 means it is already gone."""
    resp = httpx.delete(
        f"{_admin_base()}/users/{user_id}",
        headers=_auth_headers(),
        timeout=10.0,
    )
    if resp.status_code not in (204, 404):
        raise KeycloakError(f"delete user failed ({resp.status_code})")
