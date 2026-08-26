"""Fetch and cache Keycloak discovery + JWKS; verify access tokens.

JWKS is cached per realm (10 minute TTL). On an unknown ``kid`` (key rotation)
the cache entry is dropped and discovery/JWKS are fetched once more. JWKS is
always pulled from the container-internal Keycloak URL even when ``iss`` uses
the public issuer base (Docker split between KEYCLOAK_URL and KEYCLOAK_HOSTNAME).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any
from urllib.parse import urlparse

import jwt
import requests
from jwt.algorithms import RSAAlgorithm

from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable, TokenInvalid
from m8flow_backend.integrations.auth.keycloak.config import (
    keycloak_public_issuer_base,
    keycloak_url,
    spoke_client_id,
)

logger = logging.getLogger(__name__)

JWKS_CACHE_TTL_SECONDS = 600
_HTTP_TIMEOUT_SECONDS = 10
_SUPPORTED_ALGS = ("RS256",)

_cache_lock = threading.Lock()
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _internalize_url(url: str) -> str:
    public = keycloak_public_issuer_base().rstrip("/")
    internal = keycloak_url().rstrip("/")
    if public and url.startswith(public):
        return internal + url[len(public) :]
    return url


def _realm_from_issuer(issuer: str) -> str | None:
    parsed = urlparse(issuer)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "realms":
        return parts[1]
    return None


def _issuer_is_allowed(issuer: str) -> bool:
    realm = _realm_from_issuer(issuer)
    if not realm:
        return False
    allowed = {
        f"{keycloak_public_issuer_base().rstrip('/')}/realms/{realm}",
        f"{keycloak_url().rstrip('/')}/realms/{realm}",
    }
    return issuer.rstrip("/") in allowed


def _audience_is_allowed(payload: dict[str, Any]) -> bool:
    client_id = spoke_client_id()
    azp = payload.get("azp")
    aud = payload.get("aud")
    if azp == client_id:
        return True
    if isinstance(aud, str) and aud in {client_id, "account"}:
        return True
    if isinstance(aud, list) and (client_id in aud or "account" in aud):
        return True
    if aud is None and azp is None:
        return True
    return False


def _discovery_url(realm: str) -> str:
    return f"{keycloak_url().rstrip('/')}/realms/{realm}/.well-known/openid-configuration"


def _load_jwks(realm: str, *, force: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    with _cache_lock:
        cached = _jwks_cache.get(realm)
        if cached is not None and not force:
            expires_at, jwks = cached
            if expires_at > now:
                return jwks
    try:
        discovery = requests.get(_discovery_url(realm), timeout=_HTTP_TIMEOUT_SECONDS)
        discovery.raise_for_status()
        document = discovery.json()
        jwks_uri = document.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise ProviderUnavailable(f"OpenID discovery for realm {realm!r} omitted jwks_uri")
        jwks_response = requests.get(_internalize_url(jwks_uri), timeout=_HTTP_TIMEOUT_SECONDS)
        jwks_response.raise_for_status()
        jwks = jwks_response.json()
    except TokenInvalid:
        raise
    except ProviderUnavailable:
        raise
    except Exception as exc:
        raise ProviderUnavailable(f"Could not fetch JWKS for realm {realm!r}") from exc
    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise ProviderUnavailable(f"JWKS for realm {realm!r} is malformed")
    with _cache_lock:
        _jwks_cache[realm] = (now + JWKS_CACHE_TTL_SECONDS, jwks)
    return jwks


def _signing_key(jwks: dict[str, Any], kid: str | None):
    for jwk in jwks.get("keys") or []:
        if not isinstance(jwk, dict):
            continue
        if kid is not None and jwk.get("kid") != kid:
            continue
        if jwk.get("kty") != "RSA":
            continue
        return RSAAlgorithm.from_jwk(json.dumps(jwk))
    return None


def reset_jwks_cache() -> None:
    with _cache_lock:
        _jwks_cache.clear()


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify signature (JWKS), issuer, audience, and expiry. Return the payload."""
    try:
        header = jwt.get_unverified_header(token)
        unverified = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
    except jwt.PyJWTError as exc:
        raise TokenInvalid("Token is malformed") from exc

    issuer = unverified.get("iss")
    if not isinstance(issuer, str) or not _issuer_is_allowed(issuer):
        raise TokenInvalid("Token issuer is not a configured Keycloak realm")

    realm = _realm_from_issuer(issuer)
    if realm is None:
        raise TokenInvalid("Token issuer is missing a realm")

    alg = header.get("alg")
    if alg not in _SUPPORTED_ALGS:
        raise TokenInvalid(f"Unsupported token algorithm {alg!r}")

    kid = header.get("kid") if isinstance(header.get("kid"), str) else None
    jwks = _load_jwks(realm)
    key = _signing_key(jwks, kid)
    if key is None:
        jwks = _load_jwks(realm, force=True)
        key = _signing_key(jwks, kid)
    if key is None:
        raise TokenInvalid("Token signing key was not found in JWKS")

    try:
        payload = jwt.decode(
            token,
            key=key,
            algorithms=list(_SUPPORTED_ALGS),
            options={"require": ["exp", "iss"], "verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenInvalid("Token has expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise TokenInvalid("Token issuer is invalid") from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalid("Token signature verification failed") from exc

    if not _audience_is_allowed(payload):
        raise TokenInvalid("Token audience does not match the configured client")

    # jwt.decode does not re-check iss against our allow-list (we disabled
    # issuer= because public vs internal bases both occur). Repeat the check
    # on the verified payload.
    verified_iss = payload.get("iss")
    if not isinstance(verified_iss, str) or not _issuer_is_allowed(verified_iss):
        raise TokenInvalid("Token issuer is not a configured Keycloak realm")
    return payload
