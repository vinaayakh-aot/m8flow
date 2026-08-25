"""Keycloak OIDC URL builders and token grants."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import requests

from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable, TokenInvalid
from m8flow_backend.integrations.auth.base.models import TokenSet
from m8flow_backend.integrations.auth.keycloak.client_auth import build_client_assertion_jwt
from m8flow_backend.integrations.auth.keycloak.config import (
    keycloak_public_issuer_base,
    keycloak_url,
    master_client_secret,
    spoke_client_id,
    spoke_client_secret,
)

logger = logging.getLogger(__name__)

_TOKEN_TIMEOUT_SECONDS = 30


def authorization_endpoint(realm: str) -> str:
    """Browser-facing authorization URL (public issuer base, no query)."""
    if not realm or not str(realm).strip():
        raise ValueError("realm is required")
    realm = str(realm).strip()
    return f"{keycloak_public_issuer_base()}/realms/{realm}/protocol/openid-connect/auth"


def token_endpoint(realm: str) -> str:
    """Server-side token URL (container-internal Keycloak base)."""
    realm = str(realm).strip()
    return f"{keycloak_url()}/realms/{realm}/protocol/openid-connect/token"


def logout_endpoint(realm: str) -> str:
    """Browser-facing RP-initiated logout URL (public issuer base, no query)."""
    realm = str(realm).strip()
    return f"{keycloak_public_issuer_base()}/realms/{realm}/protocol/openid-connect/logout"


def build_authorization_url(
    *,
    realm: str,
    redirect_uri: str,
    state: str,
    prompt: str | None = None,
) -> str:
    params: dict[str, str] = {
        "client_id": spoke_client_id(),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    if prompt:
        params["prompt"] = prompt
    return f"{authorization_endpoint(realm)}?{urlencode(params)}"


def build_logout_url(
    *,
    realm: str,
    redirect_uri: str | None = None,
    id_token_hint: str | None = None,
) -> str:
    params: dict[str, str] = {}
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    if redirect_uri:
        params["post_logout_redirect_uri"] = redirect_uri
    if not params:
        return logout_endpoint(realm)
    return f"{logout_endpoint(realm)}?{urlencode(params)}"


def _client_secret() -> str:
    return spoke_client_secret() or master_client_secret()


def _token_set_from_response(payload: dict[str, Any]) -> TokenSet:
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise TokenInvalid("Keycloak did not return an access token")
    expires_in = payload.get("expires_in")
    refresh_expires_in = payload.get("refresh_expires_in")
    return TokenSet(
        access_token=access_token,
        refresh_token=payload.get("refresh_token") if isinstance(payload.get("refresh_token"), str) else None,
        id_token=payload.get("id_token") if isinstance(payload.get("id_token"), str) else None,
        expires_in=int(expires_in) if expires_in is not None else None,
        refresh_expires_in=int(refresh_expires_in) if refresh_expires_in is not None else None,
    )


def exchange_authorization_code(*, realm: str, code: str, redirect_uri: str) -> TokenSet:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": spoke_client_id(),
        "client_secret": _client_secret(),
    }
    return _post_token(realm, data, failure_log="authorization-code exchange")


def refresh_tokens(*, realm: str, refresh_token: str) -> TokenSet:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": spoke_client_id(),
        "client_secret": _client_secret(),
    }
    return _post_token(realm, data, failure_log="refresh")


def password_grant(*, realm: str, username: str, password: str) -> dict[str, Any]:
    """Spoke-realm resource-owner password grant using the PKCS#12 client assertion."""
    if not realm or not username:
        raise ValueError("realm and username are required")
    url = token_endpoint(realm)
    data = {
        "grant_type": "password",
        "client_id": spoke_client_id(),
        "username": username,
        "password": password,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": build_client_assertion_jwt(url, realm),
    }
    try:
        response = requests.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=_TOKEN_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 500
        if status == 401:
            raise TokenInvalid("Invalid credentials") from exc
        raise ProviderUnavailable("Keycloak password grant failed") from exc
    except requests.RequestException as exc:
        raise ProviderUnavailable("Keycloak password grant failed") from exc


def _post_token(realm: str, data: dict[str, str], *, failure_log: str) -> TokenSet:
    url = token_endpoint(realm)
    try:
        response = requests.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=_TOKEN_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise ProviderUnavailable(f"Keycloak {failure_log} request failed") from exc
    if not response.ok:
        logger.warning(
            "Keycloak %s failed: realm=%s status=%s body=%s",
            failure_log,
            realm,
            response.status_code,
            response.text[:500],
        )
        raise TokenInvalid(f"Keycloak {failure_log} was rejected")
    try:
        payload = response.json()
    except ValueError as exc:
        raise TokenInvalid(f"Keycloak {failure_log} returned non-JSON") from exc
    if not isinstance(payload, dict):
        raise TokenInvalid(f"Keycloak {failure_log} returned an unexpected payload")
    return _token_set_from_response(payload)
