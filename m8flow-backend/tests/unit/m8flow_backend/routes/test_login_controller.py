from __future__ import annotations

import ast
import base64
from urllib.parse import parse_qs, urlparse

from m8flow_backend.integrations.auth.keycloak.config import (
    keycloak_public_issuer_base,
    shared_realm_name,
    spoke_client_id,
)


def _decode_state(state: str) -> dict:
    return ast.literal_eval(base64.b64decode(state).decode("utf-8"))


def test_login_requires_redirect_url(client):
    response = client.get("/v1.0/login")
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "redirect_url_required"


def test_login_redirects_to_keycloak_with_state_and_nonce_cookie(client):
    response = client.get("/v1.0/login", query_string={"redirect_url": "http://localhost:6853/"})
    assert response.status_code == 302

    parsed = urlparse(response.headers["Location"])
    assert f"{parsed.scheme}://{parsed.netloc}" == keycloak_public_issuer_base()
    assert parsed.path == f"/realms/{shared_realm_name()}/protocol/openid-connect/auth"

    query = parse_qs(parsed.query)
    assert query["client_id"] == [spoke_client_id()]
    assert query["response_type"] == ["code"]

    state_dict = _decode_state(query["state"][0])
    assert state_dict["authentication_identifier"] == shared_realm_name()
    assert state_dict["redirect_url"] == "http://localhost:6853/"
    assert state_dict["nonce"]

    set_cookie_headers = response.headers.getlist("Set-Cookie")
    assert any(header.startswith("m8flow_oauth_nonce=") for header in set_cookie_headers)


def test_login_return_requires_state(client):
    response = client.get("/v1.0/login_return", query_string={"code": "abc"})
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_state"


def test_login_return_rejects_nonce_mismatch(client):
    login_response = client.get("/v1.0/login", query_string={"redirect_url": "http://localhost:6853/"})
    state = parse_qs(urlparse(login_response.headers["Location"]).query)["state"][0]

    # The test client's cookie jar would otherwise carry the real nonce cookie
    # set by /v1.0/login through to this request (like a browser does); clear
    # it so the callback can't match the nonce embedded in state -> rejected
    # as a forged/replayed callback.
    client.delete_cookie("m8flow_oauth_nonce", path="/v1.0/login_return")

    response = client.get("/v1.0/login_return", query_string={"state": state, "code": "abc"})
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_state"


def test_login_return_exchanges_code_and_sets_cookies(client, monkeypatch):
    login_response = client.get("/v1.0/login", query_string={"redirect_url": "http://localhost:6853/"})
    state = parse_qs(urlparse(login_response.headers["Location"]).query)["state"][0]

    captured = {}

    class _FakeTokenResponse:
        ok = True
        status_code = 200

        def json(self):
            return {"access_token": "fake-access", "id_token": "fake-id", "expires_in": 1800}

    def _fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeTokenResponse()

    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.oidc.requests.post", _fake_post)

    response = client.get("/v1.0/login_return", query_string={"state": state, "code": "auth-code-123"})

    assert response.status_code == 302
    assert response.headers["Location"] == "http://localhost:6853/"
    assert captured["data"]["grant_type"] == "authorization_code"
    assert captured["data"]["code"] == "auth-code-123"
    assert f"/realms/{shared_realm_name()}/protocol/openid-connect/token" in captured["url"]

    set_cookie_headers = response.headers.getlist("Set-Cookie")
    assert any(header.startswith("access_token=fake-access") for header in set_cookie_headers)
    assert any(header.startswith("id_token=fake-id") for header in set_cookie_headers)
    assert any(
        header.startswith(f"authentication_identifier={shared_realm_name()}") for header in set_cookie_headers
    )
    # The one-time nonce cookie must not survive a completed login.
    assert any(header.startswith("m8flow_oauth_nonce=;") for header in set_cookie_headers)


def test_login_return_sets_httponly_refresh_token_cookie(client, monkeypatch):
    login_response = client.get("/v1.0/login", query_string={"redirect_url": "http://localhost:6853/"})
    state = parse_qs(urlparse(login_response.headers["Location"]).query)["state"][0]

    class _FakeTokenResponse:
        ok = True
        status_code = 200

        def json(self):
            return {
                "access_token": "fake-access",
                "id_token": "fake-id",
                "refresh_token": "fake-refresh",
                "expires_in": 1800,
                "refresh_expires_in": 86400,
            }

    monkeypatch.setattr(
        "m8flow_backend.integrations.auth.keycloak.oidc.requests.post",
        lambda url, data=None, headers=None, timeout=None: _FakeTokenResponse(),
    )

    response = client.get("/v1.0/login_return", query_string={"state": state, "code": "auth-code-123"})

    set_cookie_headers = response.headers.getlist("Set-Cookie")
    refresh_cookie = next(
        (header for header in set_cookie_headers if header.startswith("refresh_token=fake-refresh")), None
    )
    assert refresh_cookie is not None
    assert "HttpOnly" in refresh_cookie
    assert "Max-Age=86400" in refresh_cookie

    # authentication_identifier should track the refresh token's lifetime, not
    # the (much shorter) access token's, so /v1.0/refresh can still read it
    # once the access token has expired.
    identifier_cookie = next(
        header for header in set_cookie_headers if header.startswith("authentication_identifier=")
    )
    assert "Max-Age=86400" in identifier_cookie


def test_login_return_fails_when_keycloak_rejects_the_code(client, monkeypatch):
    login_response = client.get("/v1.0/login", query_string={"redirect_url": "http://localhost:6853/"})
    state = parse_qs(urlparse(login_response.headers["Location"]).query)["state"][0]

    class _FakeErrorResponse:
        ok = False
        status_code = 400
        text = '{"error": "invalid_grant"}'

    monkeypatch.setattr(
        "m8flow_backend.integrations.auth.keycloak.oidc.requests.post",
        lambda *args, **kwargs: _FakeErrorResponse(),
    )

    response = client.get("/v1.0/login_return", query_string={"state": state, "code": "bad-code"})
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "keycloak_token_exchange_failed"


def test_login_return_surfaces_keycloak_error_param(client):
    response = client.get(
        "/v1.0/login_return",
        query_string={"error": "access_denied", "error_description": "User cancelled"},
    )
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "keycloak_login_failed"


def test_login_forwards_prompt_login_to_keycloak(client):
    response = client.get(
        "/v1.0/login",
        query_string={"redirect_url": "http://localhost:6853/", "prompt": "login"},
    )
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["Location"]).query)
    assert query["prompt"] == ["login"]


def test_logout_clears_cookies_and_redirects_to_keycloak(client):
    response = client.get(
        "/v1.0/logout",
        query_string={"redirect_url": "http://localhost:6853/", "id_token": "fake-id-token"},
    )
    assert response.status_code == 302

    parsed = urlparse(response.headers["Location"])
    assert f"{parsed.scheme}://{parsed.netloc}" == keycloak_public_issuer_base()
    assert parsed.path == f"/realms/{shared_realm_name()}/protocol/openid-connect/logout"
    query = parse_qs(parsed.query)
    assert query["id_token_hint"] == ["fake-id-token"]
    assert query["post_logout_redirect_uri"] == ["http://localhost:6853/"]

    set_cookie_headers = response.headers.getlist("Set-Cookie")
    for cookie_name in (
        "access_token",
        "id_token",
        "refresh_token",
        "authentication_identifier",
        "m8flow_selected_tenant",
        "m8flow_auth_realm",
    ):
        assert any(header.startswith(f"{cookie_name}=;") for header in set_cookie_headers), cookie_name


def test_logout_uses_authentication_identifier_for_keycloak_realm(client):
    response = client.get(
        "/v1.0/logout",
        query_string={
            "redirect_url": "http://localhost:6853/",
            "id_token": "fake-id-token",
            "authentication_identifier": "master",
        },
    )
    assert response.status_code == 302
    parsed = urlparse(response.headers["Location"])
    assert parsed.path == "/realms/master/protocol/openid-connect/logout"


def test_logout_backend_only_skips_keycloak(client):
    response = client.get(
        "/v1.0/logout",
        query_string={"redirect_url": "http://localhost:6853/", "backend_only": "true"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "http://localhost:6853/"


def test_refresh_requires_refresh_token_cookie(client):
    response = client.post("/v1.0/refresh")
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "no_refresh_token"


def test_refresh_mints_new_tokens_from_refresh_token_cookie(client, monkeypatch):
    client.set_cookie("refresh_token", "fake-refresh", path="/")
    client.set_cookie("authentication_identifier", shared_realm_name(), path="/")

    captured = {}

    class _FakeTokenResponse:
        ok = True
        status_code = 200

        def json(self):
            return {
                "access_token": "fresh-access",
                "id_token": "fresh-id",
                "refresh_token": "fresh-refresh",
                "expires_in": 1800,
                "refresh_expires_in": 86400,
            }

    def _fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeTokenResponse()

    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.oidc.requests.post", _fake_post)

    response = client.post("/v1.0/refresh")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert captured["data"]["grant_type"] == "refresh_token"
    assert captured["data"]["refresh_token"] == "fake-refresh"
    assert f"/realms/{shared_realm_name()}/protocol/openid-connect/token" in captured["url"]

    set_cookie_headers = response.headers.getlist("Set-Cookie")
    assert any(header.startswith("access_token=fresh-access") for header in set_cookie_headers)
    assert any(header.startswith("refresh_token=fresh-refresh") for header in set_cookie_headers)


def test_refresh_fails_when_keycloak_rejects_the_refresh_token(client, monkeypatch):
    client.set_cookie("refresh_token", "expired-refresh", path="/")

    class _FakeErrorResponse:
        ok = False
        status_code = 400
        text = '{"error": "invalid_grant"}'

    monkeypatch.setattr(
        "m8flow_backend.integrations.auth.keycloak.oidc.requests.post",
        lambda *args, **kwargs: _FakeErrorResponse(),
    )

    response = client.post("/v1.0/refresh")
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "keycloak_refresh_failed"
