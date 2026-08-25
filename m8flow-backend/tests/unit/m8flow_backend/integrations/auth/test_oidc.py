from __future__ import annotations

import pytest
import requests

from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable, TokenInvalid
from m8flow_backend.integrations.auth.keycloak import oidc


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self) -> None:
        error = requests.HTTPError(f"http {self.status_code}")
        error.response = self
        raise error

    def json(self) -> dict:
        return {}


def test_password_grant_maps_401_to_token_invalid(monkeypatch):
    monkeypatch.setattr(oidc, "build_client_assertion_jwt", lambda *args, **kwargs: "jwt")
    monkeypatch.setattr(oidc, "spoke_client_id", lambda: "spoke")
    monkeypatch.setattr(oidc.requests, "post", lambda *args, **kwargs: _FakeResponse(401))
    with pytest.raises(TokenInvalid):
        oidc.password_grant(realm="m8flow", username="ada", password="bad")


def test_password_grant_maps_other_http_errors_to_unavailable(monkeypatch):
    monkeypatch.setattr(oidc, "build_client_assertion_jwt", lambda *args, **kwargs: "jwt")
    monkeypatch.setattr(oidc, "spoke_client_id", lambda: "spoke")
    monkeypatch.setattr(oidc.requests, "post", lambda *args, **kwargs: _FakeResponse(503))
    with pytest.raises(ProviderUnavailable):
        oidc.password_grant(realm="m8flow", username="ada", password="bad")
