"""Thin Keycloak Admin API client.

Authenticates as a service-account client (client_credentials grant) and
talks to the Keycloak Admin REST API. Shared by the notification function
(email lookup) and user-service (account deletion).

The service account needs the relevant `realm-management` client roles:
`view-users` for lookups, `manage-users` to delete.
"""
from __future__ import annotations

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

KC_URL = os.environ.get("KEYCLOAK_URL", "")
KC_REALM = os.environ.get("KEYCLOAK_REALM", "")
KC_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "")
KC_CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", "")

_token_cache: dict = {"access_token": None, "exp": 0.0}


def _admin_token() -> str:
    if (
        _token_cache["access_token"]
        and _token_cache["exp"] > time.time() + 30
    ):
        return _token_cache["access_token"]

    resp = requests.post(
        f"{KC_URL}/realms/{KC_REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": KC_CLIENT_ID,
            "client_secret": KC_CLIENT_SECRET,
        },
        timeout=5,
    )
    resp.raise_for_status()
    tok = resp.json()
    _token_cache.update(
        access_token=tok["access_token"],
        exp=time.time() + tok["expires_in"],
    )
    return tok["access_token"]


def get_user_email(user_id: str) -> str | None:
    """Return the user's email, or None if the user doesn't exist."""
    resp = requests.get(
        f"{KC_URL}/admin/realms/{KC_REALM}/users/{user_id}",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        timeout=5,
    )
    if resp.status_code == 404:
        return None
    if resp.status_code == 401:
        # Token may have been revoked — bust cache and retry once.
        _token_cache["access_token"] = None
        resp = requests.get(
            f"{KC_URL}/admin/realms/{KC_REALM}/users/{user_id}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
            timeout=5,
        )
    resp.raise_for_status()
    return resp.json().get("email")


def delete_user(user_id: str) -> bool:
    """Delete a Keycloak user. Returns False if the user didn't exist.

    Requires the service account to have `manage-users`.
    """
    resp = requests.delete(
        f"{KC_URL}/admin/realms/{KC_REALM}/users/{user_id}",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        timeout=5,
    )
    if resp.status_code == 401:
        # Token may have been revoked — bust cache and retry once.
        _token_cache["access_token"] = None
        resp = requests.delete(
            f"{KC_URL}/admin/realms/{KC_REALM}/users/{user_id}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
            timeout=5,
        )
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    return True
