"""Keycloak Admin API directory: realm users.

Tenant/membership HTTP lives in ``tenants.py``. The provider only returns
neutral objects.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import requests

from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable, UserNotFound
from m8flow_backend.integrations.auth.base.models import User
from m8flow_backend.integrations.auth.keycloak.client_auth import fetch_master_admin_token
from m8flow_backend.integrations.auth.keycloak.config import keycloak_url

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 30


def user_from_representation(payload: dict[str, Any]) -> User:
    user_id = payload.get("id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ProviderUnavailable("Directory user is missing a subject")
    username = payload.get("username")
    email = payload.get("email")
    first = payload.get("firstName") if isinstance(payload.get("firstName"), str) else ""
    last = payload.get("lastName") if isinstance(payload.get("lastName"), str) else ""
    display = f"{first} {last}".strip() or None
    return User(
        subject=user_id.strip(),
        username=username.strip() if isinstance(username, str) and username.strip() else None,
        email=email.strip() if isinstance(email, str) and email.strip() else None,
        display_name=display,
    )


def _admin_token(admin_token: str | None) -> str:
    return admin_token or fetch_master_admin_token()


def _users_collection_url(realm: str) -> str:
    return f"{keycloak_url()}/admin/realms/{realm}/users"


def _user_url(realm: str, user_id: str) -> str:
    return f"{_users_collection_url(realm)}/{quote(user_id, safe='')}"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def fetch_user_representation(
    realm: str,
    username: str,
    *,
    admin_token: str | None = None,
) -> dict[str, Any] | None:
    """Return the exact-match user representation, or None if missing/ambiguous."""
    if not realm or not str(realm).strip():
        raise ValueError("realm is required")
    if not username or not str(username).strip():
        raise ValueError("username is required")
    normalized_realm = str(realm).strip()
    normalized_username = str(username).strip()
    try:
        response = requests.get(
            _users_collection_url(normalized_realm),
            params={"username": normalized_username, "exact": "true", "max": 100},
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        users = response.json()
    except requests.RequestException as exc:
        raise ProviderUnavailable(f"Could not look up directory user {normalized_username!r}") from exc
    if not isinstance(users, list):
        return None
    exact = [
        user
        for user in users
        if isinstance(user, dict) and user.get("username") == normalized_username
    ]
    if len(exact) != 1:
        return None
    return exact[0]


def search_user_representations(
    realm: str,
    search: str,
    *,
    exact: bool = False,
    admin_token: str | None = None,
    max_results: int = 100,
    first_result: int = 0,
) -> list[dict[str, Any]]:
    if not realm or not str(realm).strip():
        raise ValueError("realm is required")
    normalized_realm = str(realm).strip()
    normalized_search = str(search).strip() if isinstance(search, str) else ""
    params: dict[str, Any] = {"max": max_results}
    if first_result > 0:
        params["first"] = first_result
    if normalized_search:
        params["search"] = normalized_search
        params["exact"] = "true" if exact else "false"
    try:
        response = requests.get(
            _users_collection_url(normalized_realm),
            params=params,
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        users = response.json()
    except requests.RequestException as exc:
        raise ProviderUnavailable(f"Could not search directory users in realm {normalized_realm!r}") from exc
    if not isinstance(users, list):
        return []
    return [user for user in users if isinstance(user, dict)]


def create_user(
    realm: str,
    username: str,
    password: str,
    *,
    email: str | None = None,
    enabled: bool = True,
    admin_token: str | None = None,
) -> User:
    """Create a realm user, clear required actions, return the neutral User."""
    if not realm or not username:
        raise ValueError("realm and username are required")
    normalized_realm = str(realm).strip()
    normalized_username = str(username).strip()
    token = _admin_token(admin_token)
    payload: dict[str, Any] = {
        "username": normalized_username,
        "enabled": enabled,
        "emailVerified": True,
        "firstName": normalized_username,
        "lastName": "User",
        "credentials": [{"type": "password", "value": password, "temporary": False}],
        "requiredActions": [],
    }
    if email:
        payload["email"] = email
    try:
        response = requests.post(
            _users_collection_url(normalized_realm),
            json=payload,
            headers=_headers(token),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code == 409:
            raise ProviderUnavailable("User already exists")
        response.raise_for_status()
        location = response.headers.get("Location")
        if not (location and location.strip()):
            raise ProviderUnavailable("Directory did not return a user location after create")
        user_id = location.strip().rstrip("/").split("/")[-1]
        get_response = requests.get(
            _user_url(normalized_realm, user_id),
            headers=_headers(token),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        get_response.raise_for_status()
        user_data = get_response.json()
        if not isinstance(user_data, dict):
            raise ProviderUnavailable("Directory returned a malformed user after create")
        user_data["requiredActions"] = []
        user_data["emailVerified"] = True
        if not user_data.get("firstName"):
            user_data["firstName"] = normalized_username
        if not user_data.get("lastName"):
            user_data["lastName"] = "User"
        put_response = requests.put(
            _user_url(normalized_realm, user_id),
            json=user_data,
            headers=_headers(token),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        put_response.raise_for_status()
        return user_from_representation(user_data)
    except ProviderUnavailable:
        raise
    except requests.RequestException as exc:
        raise ProviderUnavailable(f"Could not create directory user {normalized_username!r}") from exc


def delete_user_by_id(
    realm: str,
    user_id: str,
    *,
    admin_token: str | None = None,
) -> None:
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id is required")
    normalized_realm = str(realm).strip()
    normalized_user_id = str(user_id).strip()
    try:
        response = requests.delete(
            _user_url(normalized_realm, normalized_user_id),
            headers={"Authorization": f"Bearer {_admin_token(admin_token)}"},
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            logger.info(
                "Directory user %s already deleted or not found in realm %s.",
                normalized_user_id,
                normalized_realm,
            )
            return
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderUnavailable(f"Could not delete directory user {normalized_user_id!r}") from exc
    logger.info("Deleted directory user %s from realm %s.", normalized_user_id, normalized_realm)


def delete_user_by_username(
    realm: str,
    username: str,
    *,
    admin_token: str | None = None,
) -> None:
    representation = fetch_user_representation(realm, username, admin_token=admin_token)
    if representation is None:
        raise UserNotFound(username)
    user_id = representation.get("id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ProviderUnavailable("Directory user is missing a subject")
    delete_user_by_id(realm, user_id, admin_token=admin_token)
