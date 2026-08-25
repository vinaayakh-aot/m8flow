"""PKCS#12 client-assertion JWT and master-realm admin token.

The provider owns Keycloak client authentication.
"""
from __future__ import annotations

import logging
import time
import uuid
import warnings

import jwt
import requests

from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable
from m8flow_backend.integrations.auth.keycloak.config import (
    keycloak_admin_password,
    keycloak_admin_user,
    keycloak_url,
    spoke_client_id,
    spoke_keystore_p12_path,
    spoke_keystore_password,
)

logger = logging.getLogger(__name__)


def load_spoke_p12_private_key():
    """Load the private key (and cert) from the configured PKCS#12 keystore."""
    path = spoke_keystore_p12_path()
    if not path:
        raise ValueError(
            "M8FLOW_KEYCLOAK_SPOKE_KEYSTORE_P12 path is not set or the file was not found. "
            "Set M8FLOW_KEYCLOAK_SPOKE_KEYSTORE_P12 to m8flow-backend/keystore.p12 "
            "(or an absolute path) for spoke tenant auth."
        )
    password = spoke_keystore_password()
    if not password:
        raise ValueError("M8FLOW_KEYCLOAK_SPOKE_KEYSTORE_PASSWORD must be set for JWT client assertion.")
    from cryptography.hazmat.primitives.serialization import pkcs12

    with open(path, "rb") as handle:
        data = handle.read()
    password_bytes = password.encode("utf-8") if isinstance(password, str) else password
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="PKCS#12 bundle could not be parsed as DER")
        private_key, certificate, _ = pkcs12.load_key_and_certificates(data, password_bytes)
    if private_key is None:
        raise ValueError("keystore.p12 has no private key")
    return private_key, certificate


def spoke_certificate_pem() -> str:
    """Public certificate PEM from the PKCS#12 keystore (JWT client auth)."""
    _, certificate = load_spoke_p12_private_key()
    if certificate is None:
        raise ValueError("keystore.p12 has no certificate")
    from cryptography.hazmat.primitives.serialization import Encoding

    return certificate.public_bytes(Encoding.PEM).decode("utf-8")


def build_client_assertion_jwt(token_url: str, realm: str) -> str:
    """RFC 7523 client_assertion JWT, signed with the spoke keystore private key."""
    base_url = keycloak_url()
    realm_issuer = f"{base_url}/realms/{realm}"
    client_id = spoke_client_id()
    now = int(time.time())
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": realm_issuer,
        "exp": now + 60,
        "iat": now,
        "jti": f"{uuid.uuid4().hex}-{now}-{uuid.uuid4().hex[:8]}",
    }
    private_key, _ = load_spoke_p12_private_key()
    return jwt.encode(payload, private_key, algorithm="RS256")


def fetch_master_admin_token() -> str:
    """Access token via master-realm admin username/password (Admin API)."""
    url = f"{keycloak_url()}/realms/master/protocol/openid-connect/token"
    password = keycloak_admin_password()
    if not password:
        raise ValueError(
            "KEYCLOAK_ADMIN_PASSWORD or M8FLOW_KEYCLOAK_ADMIN_PASSWORD must be set for realm creation."
        )
    username = keycloak_admin_user()
    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": username,
        "password": password,
    }
    try:
        response = requests.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as exc:
        raise ProviderUnavailable("Could not obtain Keycloak master admin token") from exc
