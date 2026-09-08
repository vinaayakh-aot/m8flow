"""Shared session-cookie shape for every path that mints or refreshes a
Keycloak token set: browser-redirect login (login_controller.py) and the
in-session tenant switch (auth.try_finalize_shared_realm_session, which
refresh-remints the token after writing the active-org attribute).
"""
from __future__ import annotations

from flask import Response

from m8flow_backend.integrations.auth.base.models import TokenSet

SESSION_COOKIE_NAMES = ("access_token", "id_token", "refresh_token", "authentication_identifier")
DEFAULT_REFRESH_TOKEN_MAX_AGE = 86400  # falls back to the realm's ssoSessionIdleTimeout default


def token_set_as_dict(token_set: TokenSet) -> dict:
    payload: dict = {"access_token": token_set.access_token}
    if token_set.id_token:
        payload["id_token"] = token_set.id_token
    if token_set.refresh_token:
        payload["refresh_token"] = token_set.refresh_token
    if token_set.expires_in is not None:
        payload["expires_in"] = token_set.expires_in
    if token_set.refresh_expires_in is not None:
        payload["refresh_expires_in"] = token_set.refresh_expires_in
    return payload


def clear_session_cookies(response: Response) -> None:
    for cookie_name in SESSION_COOKIE_NAMES:
        response.set_cookie(cookie_name, "", max_age=0, path="/")


def set_token_cookies(response: Response, tokens: dict, *, identifier: str) -> None:
    """Set the session cookies from a Keycloak token response.

    Shared by login_return (authorization_code grant), refresh (refresh_token
    grant), and the in-session tenant switch (auth.try_finalize_shared_realm_session,
    a refresh_token grant after writing the active-org attribute) -- all keep the
    same cookie shape.
    """
    access_max_age = int(tokens.get("expires_in") or 1800)

    access_token = tokens.get("access_token")
    # Non-httpOnly: m8flow-frontend/m8flow-designer read these directly via
    # document.cookie (see m8flow-frontend/src/services/UserService.ts).
    response.set_cookie("access_token", access_token, max_age=access_max_age, path="/", samesite="Lax")

    id_token = tokens.get("id_token")
    if id_token:
        response.set_cookie("id_token", id_token, max_age=access_max_age, path="/", samesite="Lax")

    refresh_token = tokens.get("refresh_token")
    # httpOnly, unlike the two cookies above: the frontend never reads this
    # value itself, only round-trips it via /v1.0/refresh's cookie jar
    # (`credentials: 'include'`).
    identifier_max_age = access_max_age
    if refresh_token:
        identifier_max_age = int(tokens.get("refresh_expires_in") or DEFAULT_REFRESH_TOKEN_MAX_AGE)
        response.set_cookie(
            "refresh_token",
            refresh_token,
            max_age=identifier_max_age,
            path="/",
            samesite="Lax",
            httponly=True,
        )

    # Tracks the refresh token's lifetime (not the access token's): this cookie
    # only needs to outlive the access token long enough for /v1.0/refresh to
    # know which realm to ask, and a refresh attempt is exactly what happens
    # once the access token has already expired.
    response.set_cookie("authentication_identifier", identifier, max_age=identifier_max_age, path="/", samesite="Lax")
