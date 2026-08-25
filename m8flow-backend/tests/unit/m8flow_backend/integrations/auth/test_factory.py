from __future__ import annotations

import pytest

from m8flow_backend.integrations.auth.base.errors import AuthProviderError, TokenInvalid
from m8flow_backend.integrations.auth.base.provider import AuthProvider
from m8flow_backend.integrations.auth.factory import (
    AUTH_PROVIDER_ENV,
    get_auth_provider,
    register_auth_provider,
    reset_auth_provider,
)
from m8flow_backend.integrations.auth.keycloak.provider import KeycloakAuthProvider


@pytest.fixture(autouse=True)
def _reset_provider():
    reset_auth_provider()
    yield
    reset_auth_provider()


def test_get_auth_provider_defaults_to_keycloak():
    provider = get_auth_provider()
    assert isinstance(provider, KeycloakAuthProvider)
    assert get_auth_provider() is provider


def test_keycloak_provider_session_methods_are_implemented():
    provider = KeycloakAuthProvider()
    with pytest.raises(TokenInvalid):
        provider.verify_token("not-a-jwt")
    assert callable(provider.directory_admin.create_user)
    assert callable(provider.directory_admin.delete_user)
    assert callable(provider.directory_admin.get_tenant)
    assert callable(provider.directory_admin.create_tenant)
    assert callable(provider.directory_admin.add_member)
    assert callable(provider.provisioning.create_tenant_realm)
    assert callable(provider.provisioning.delete_tenant_realm)
    assert callable(provider.provisioning.ensure_client_redirect_uri)


def test_unknown_provider_name_raises(monkeypatch):
    monkeypatch.setenv(AUTH_PROVIDER_ENV, "not-a-provider")
    with pytest.raises(AuthProviderError, match="Unknown auth provider"):
        get_auth_provider()


def test_register_auth_provider_is_selectable_without_touching_call_sites(monkeypatch):
    class FakeProvider(AuthProvider):
        pass

    register_auth_provider("fake", FakeProvider)
    monkeypatch.setenv(AUTH_PROVIDER_ENV, "fake")
    reset_auth_provider()
    assert isinstance(get_auth_provider(), FakeProvider)


def test_create_app_exposes_keycloak_provider(app):
    assert isinstance(app.extensions["auth_provider"], KeycloakAuthProvider)
