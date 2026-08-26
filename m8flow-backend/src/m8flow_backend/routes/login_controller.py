# m8flow-backend/src/m8flow_backend/routes/login_controller.py
"""Browser-redirect Keycloak login/logout.

`POST /v1.0/login` (routes/v1.py) is a JSON credentials endpoint that mints an
internal token directly — it does not talk to Keycloak. This module is the
other kind of login: the one a browser hits by full-page redirect.

  1. `GET /v1.0/login` sends the browser to Keycloak's hosted login page.
  2. Keycloak redirects back to `GET /v1.0/login_return` with an authorization
     code.
  3. This exchanges the code for tokens (server-side, using the confidential
     `m8flow-backend` Keycloak client) and sets `access_token`/`id_token`/
     `refresh_token` cookies, then redirects to the caller's original
     `redirect_url`.
  4. `POST /v1.0/refresh` silently mints a fresh `access_token`/`id_token`
     from the `refresh_token` cookie. m8flow-frontend's HttpService tries this
     first on a 401 before falling back to a full `GET /v1.0/login` redirect —
     see HttpService.ts. Without it, every access-token expiry (30 min of
     idle) forced a full round trip through Keycloak's `/auth` endpoint, which
     is where a known Keycloak quirk (a still-live AUTH_SESSION_ID/KC_RESTART
     cookie pointing at an already-evicted server-side auth session) can
     surface as Keycloak's own "loginTimeout" error page.
  5. `GET /v1.0/logout` clears those cookies and ends the Keycloak SSO session.

This gap was later filled by this module.
"""
from __future__ import annotations

import ast
import base64
import secrets
from urllib.parse import unquote

from flask import Response, jsonify, redirect, request

from m8flow_backend.integrations.auth.keycloak.config import shared_realm_name
from m8flow_backend.errors import ApiError
from m8flow_backend.integrations.auth import get_auth_provider
from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable, TokenInvalid
from m8flow_backend.integrations.auth.base.models import TokenSet
from m8flow_backend.tenancy import SELECTED_TENANT_COOKIE_NAME

_OAUTH_NONCE_COOKIE = "m8flow_oauth_nonce"
_LOGIN_RETURN_PATH = "/v1.0/login_return"
_SESSION_COOKIE_NAMES = ("access_token", "id_token", "refresh_token", "authentication_identifier")
_DEFAULT_REFRESH_TOKEN_MAX_AGE = 86400  # falls back to the realm's ssoSessionIdleTimeout default


def _token_set_as_dict(token_set: TokenSet) -> dict:
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


def _redirect_uri() -> str:
    """Callback URL registered on the m8flow-backend client (its redirectUris
    entry is a wildcard on this backend's own origin, e.g. http://localhost:6840/*)."""
    return f"{request.host_url.rstrip('/')}{_LOGIN_RETURN_PATH}"


def _encode_state(*, authentication_identifier: str, redirect_url: str, nonce: str) -> str:
    """Base64-encode a Python dict repr for the OAuth `state` param.

    This matches the format m8flow_backend.services.tenant_context_middleware
    already decodes (base64 -> ast.literal_eval) so a `state` minted here stays
    readable by that tenant-resolution code if it's ever wired back in — at no
    extra cost today, since nothing currently requires it.
    """
    state_dict = {
        "authentication_identifier": authentication_identifier,
        "redirect_url": redirect_url,
        "nonce": nonce,
    }
    return base64.b64encode(str(state_dict).encode("utf-8")).decode("ascii")


def _decode_state(state: str | None) -> dict[str, str] | None:
    if not state:
        return None
    try:
        raw = base64.b64decode(unquote(state)).decode("utf-8")
        state_dict = ast.literal_eval(raw)
    except Exception:
        return None
    return state_dict if isinstance(state_dict, dict) else None


def _clear_session_cookies(response: Response) -> None:
    for cookie_name in _SESSION_COOKIE_NAMES:
        response.set_cookie(cookie_name, "", max_age=0, path="/")


def _set_token_cookies(response: Response, tokens: dict, *, identifier: str) -> None:
    """Set the session cookies from a Keycloak token response.

    Shared by login_return (authorization_code grant) and refresh
    (refresh_token grant) so both keep the same cookie shape.
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
        identifier_max_age = int(tokens.get("refresh_expires_in") or _DEFAULT_REFRESH_TOKEN_MAX_AGE)
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


def login() -> Response:
    """GET /v1.0/login - start the browser-redirect Keycloak login flow.

    Query params:
      redirect_url (required): where to land in the app after a successful login.
      authentication_identifier (optional): realm to authenticate against;
        defaults to the shared realm.
    """
    redirect_url = request.args.get("redirect_url")
    if not redirect_url:
        raise ApiError("redirect_url_required", "redirect_url is required", 400)

    identifier = (request.args.get("authentication_identifier") or "").strip() or shared_realm_name()
    nonce = secrets.token_urlsafe(24)
    state = _encode_state(authentication_identifier=identifier, redirect_url=redirect_url, nonce=nonce)

    # Optional OIDC prompt (e.g. login) — used after logout so a leftover SSO
    # session in another realm cannot silently re-authenticate.
    prompt = (request.args.get("prompt") or "").strip() or None
    auth_url = get_auth_provider().build_login_url(
        redirect_uri=_redirect_uri(),
        state=state,
        authentication_identifier=identifier,
        prompt=prompt,
    )

    response = redirect(auth_url)
    # httpOnly + scoped to the callback path: only ever read back by login_return,
    # never needed (or wanted) in frontend JS.
    response.set_cookie(
        _OAUTH_NONCE_COOKIE,
        nonce,
        max_age=300,
        path=_LOGIN_RETURN_PATH,
        httponly=True,
        samesite="Lax",
    )
    return response


def login_return() -> Response:
    """GET /v1.0/login_return - Keycloak's OAuth authorization-code callback."""
    error = request.args.get("error")
    if error:
        raise ApiError("keycloak_login_failed", request.args.get("error_description") or error, 401)

    state = _decode_state(request.args.get("state"))
    if not state:
        raise ApiError("invalid_state", "Missing or malformed state parameter", 400)

    nonce_cookie = request.cookies.get(_OAUTH_NONCE_COOKIE)
    if not nonce_cookie or nonce_cookie != state.get("nonce"):
        raise ApiError("invalid_state", "state did not match the expected login attempt", 400)

    code = request.args.get("code")
    if not code:
        raise ApiError("missing_code", "code is required", 400)

    identifier = state.get("authentication_identifier") or shared_realm_name()
    redirect_url = state.get("redirect_url") or "/"

    try:
        token_set = get_auth_provider().exchange_code(
            code=code,
            redirect_uri=_redirect_uri(),
            authentication_identifier=identifier,
        )
    except (TokenInvalid, ProviderUnavailable):
        raise ApiError("keycloak_token_exchange_failed", "Could not complete sign-in", 401) from None

    response = redirect(redirect_url)
    response.set_cookie(_OAUTH_NONCE_COOKIE, "", max_age=0, path=_LOGIN_RETURN_PATH)
    _set_token_cookies(response, _token_set_as_dict(token_set), identifier=identifier)
    return response


def refresh() -> Response:
    """POST /v1.0/refresh - silently mint fresh tokens from the refresh_token
    cookie, without sending the browser back through Keycloak's /auth
    endpoint. See the module docstring for why this exists.

    Returns 401 (no cookies changed) if there's no refresh_token cookie or
    Keycloak rejects it (expired/revoked); the caller is expected to fall
    back to the full GET /v1.0/login redirect in that case.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise ApiError("no_refresh_token", "No refresh token cookie present", 401)

    identifier = request.cookies.get("authentication_identifier") or shared_realm_name()

    try:
        token_set = get_auth_provider().refresh(
            refresh_token=refresh_token,
            authentication_identifier=identifier,
        )
    except (TokenInvalid, ProviderUnavailable):
        raise ApiError("keycloak_refresh_failed", "Could not refresh session", 401) from None

    response = jsonify({"ok": True})
    _set_token_cookies(response, _token_set_as_dict(token_set), identifier=identifier)
    return response


def logout() -> Response:
    """GET /v1.0/logout - clear the app session and end the Keycloak SSO session.

    Query params (matching m8flow-frontend's UserService.doLogout()):
      redirect_url: where to land after logout.
      id_token: the session's id_token, used as Keycloak's id_token_hint.
      authentication_identifier (optional): defaults to the session's cookie,
        then the shared realm.
      backend_only=true (optional): skip the Keycloak round trip entirely
        (used for anonymous/public-user sessions with no real Keycloak login).
    """
    redirect_url = request.args.get("redirect_url") or "/"
    identifier = (
        request.args.get("authentication_identifier")
        or request.cookies.get("authentication_identifier")
        or shared_realm_name()
    )
    id_token = request.args.get("id_token") or request.cookies.get("id_token")
    backend_only = (request.args.get("backend_only") or "").strip().lower() == "true"

    if not backend_only and id_token:
        target = get_auth_provider().build_logout_url(
            authentication_identifier=identifier,
            redirect_uri=redirect_url,
            id_token_hint=id_token,
        )
    else:
        target = redirect_url

    response = redirect(target)
    _clear_session_cookies(response)
    response.set_cookie("m8flow_auth_realm", "", max_age=0, path="/")
    # A full logout should not let the next sign-in silently inherit the
    # previous session's tenant selection.
    response.set_cookie(SELECTED_TENANT_COOKIE_NAME, "", max_age=0, path="/")
    return response
