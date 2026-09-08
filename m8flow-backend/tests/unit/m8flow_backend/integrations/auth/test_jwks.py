from __future__ import annotations

import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from m8flow_backend.auth import (
    JWT_ALGORITHM,
    LOCAL_TOKEN_AUDIENCE,
    decode_auth_token,
    jwt_secret,
)
from m8flow_backend.integrations.auth.base.errors import TokenInvalid
from m8flow_backend.integrations.auth.keycloak.config import (
    keycloak_public_issuer_base,
    keycloak_url,
    shared_realm_name,
    spoke_client_id,
)
from m8flow_backend.integrations.auth.keycloak.jwks import reset_jwks_cache, verify_access_token
from m8flow_backend.integrations.auth.keycloak.provider import KeycloakAuthProvider


@pytest.fixture(autouse=True)
def _jwks_env(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak.internal")
    monkeypatch.setenv("KEYCLOAK_HOSTNAME", "http://keycloak.public")
    reset_jwks_cache()
    yield
    reset_jwks_cache()


def _rsa_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = "test-kid"
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"
    return private_key, public_jwk


def _issue(*, private_key, kid: str = "test-kid", **claims) -> str:
    now = int(time.time())
    payload = {
        "sub": "user-1",
        "iss": f"{keycloak_public_issuer_base()}/realms/{shared_realm_name()}",
        "azp": spoke_client_id(),
        "preferred_username": "editor",
        "iat": now,
        "exp": now + 3600,
    }
    payload.update(claims)
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


class _FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._payload


def _patch_jwks(monkeypatch, jwk: dict[str, Any]) -> None:
    internal = keycloak_url().rstrip("/")
    realm = shared_realm_name()
    discovery_url = f"{internal}/realms/{realm}/.well-known/openid-configuration"
    jwks_uri = f"{internal}/realms/{realm}/protocol/openid-connect/certs"

    def _fake_get(url, timeout=None):
        if url == discovery_url:
            return _FakeResponse({"jwks_uri": jwks_uri})
        if url == jwks_uri:
            return _FakeResponse({"keys": [jwk]})
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(
        "m8flow_backend.integrations.auth.keycloak.jwks.requests.get",
        _fake_get,
    )


def test_verify_token_accepts_valid_rs256_access_token(monkeypatch):
    private_key, jwk = _rsa_pair()
    _patch_jwks(monkeypatch, jwk)
    token = _issue(private_key=private_key)

    payload = verify_access_token(token)
    assert payload["sub"] == "user-1"
    claims = KeycloakAuthProvider().verify_token(token)
    assert claims.subject == "user-1"
    assert claims.username == "editor"
    assert claims.jwt_claims["sub"] == "user-1"


def test_verify_token_rejects_bad_signature(monkeypatch):
    private_key, jwk = _rsa_pair()
    other_key, _ = _rsa_pair()
    _patch_jwks(monkeypatch, jwk)
    token = _issue(private_key=other_key)
    with pytest.raises(TokenInvalid, match="signature"):
        verify_access_token(token)


def test_verify_token_rejects_wrong_issuer(monkeypatch):
    private_key, jwk = _rsa_pair()
    _patch_jwks(monkeypatch, jwk)
    token = _issue(private_key=private_key, iss="http://evil.example/realms/m8flow")
    with pytest.raises(TokenInvalid, match="issuer"):
        verify_access_token(token)


def test_verify_token_rejects_expired_token(monkeypatch):
    private_key, jwk = _rsa_pair()
    _patch_jwks(monkeypatch, jwk)
    token = _issue(private_key=private_key, exp=int(time.time()) - 10, iat=int(time.time()) - 40)
    with pytest.raises(TokenInvalid, match="expired"):
        verify_access_token(token)


def test_provider_verify_token_rejects_bad_signature(monkeypatch):
    private_key, jwk = _rsa_pair()
    other_key, _ = _rsa_pair()
    _patch_jwks(monkeypatch, jwk)
    token = _issue(private_key=other_key)
    with pytest.raises(TokenInvalid):
        KeycloakAuthProvider().verify_token(token)


def test_provider_verify_token_rejects_wrong_issuer(monkeypatch):
    private_key, jwk = _rsa_pair()
    _patch_jwks(monkeypatch, jwk)
    token = _issue(private_key=private_key, iss="http://evil.example/realms/m8flow")
    with pytest.raises(TokenInvalid):
        KeycloakAuthProvider().verify_token(token)


def test_provider_verify_token_rejects_expired_token(monkeypatch):
    private_key, jwk = _rsa_pair()
    _patch_jwks(monkeypatch, jwk)
    token = _issue(private_key=private_key, exp=int(time.time()) - 10, iat=int(time.time()) - 40)
    with pytest.raises(TokenInvalid):
        KeycloakAuthProvider().verify_token(token)


def _host_token(secret: str | None = None, **overrides) -> str:
    now = int(time.time())
    payload = {
        "sub": "service:local::service_id:u1",
        "iat": now,
        "exp": now + 60,
        "iss": "local-service",
        "aud": LOCAL_TOKEN_AUDIENCE,
    }
    payload.update(overrides)
    return jwt.encode(payload, secret or jwt_secret(), algorithm=JWT_ALGORITHM)


def test_decode_auth_token_still_accepts_hs256_host_tokens():
    token = _host_token()
    assert decode_auth_token(token)["sub"] == "service:local::service_id:u1"


def test_decode_auth_token_rejects_forged_unsigned_payload():
    token = _host_token(secret="wrong-secret-must-be-32-bytes-min!!")
    with pytest.raises(jwt.InvalidTokenError):
        decode_auth_token(token)


def test_decode_auth_token_rejects_host_token_without_audience():
    # A host HS256 token missing its audience binding must be rejected.
    token = jwt.encode(
        {"sub": "service:local::service_id:u1", "iat": int(time.time()), "exp": int(time.time()) + 60, "iss": "local-service"},
        jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_auth_token(token)


def test_decode_auth_token_rejects_host_token_with_wrong_audience():
    token = _host_token(aud="some-other-service")
    with pytest.raises(jwt.InvalidTokenError):
        decode_auth_token(token)


def test_jwt_secret_fails_hard_when_unset(monkeypatch):
    monkeypatch.delenv("FLASK_SESSION_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FLASK_SESSION_SECRET_KEY"):
        jwt_secret()


def test_audience_rejects_unbound_and_account_only(monkeypatch):
    private_key, jwk = _rsa_pair()
    _patch_jwks(monkeypatch, jwk)
    # No azp and no aud -> previously allowed (unbound token), now rejected.
    unbound = _issue(private_key=private_key, azp=None, aud=None)
    with pytest.raises(TokenInvalid, match="audience"):
        verify_access_token(unbound)
    # Only the generic "account" audience, azp for a different client -> rejected.
    account_only = _issue(private_key=private_key, azp="some-other-client", aud=["account"])
    with pytest.raises(TokenInvalid, match="audience"):
        verify_access_token(account_only)
