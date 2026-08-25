from __future__ import annotations

from typing import Any

import pytest
import requests

from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable
from m8flow_backend.integrations.auth.base.models import Group, TenantRef
from m8flow_backend.integrations.auth.keycloak.provider import KeycloakAuthProvider
from m8flow_backend.integrations.auth.keycloak.role_mapping import tenant_roles_for_organization_group


ORGS_URL = "http://keycloak.internal/admin/realms/m8flow/organizations"
GROUPS_URL = f"{ORGS_URL}/org-1/groups"
USERS_URL = "http://keycloak.internal/admin/realms/m8flow/users"


class _FakeResponse:
    def __init__(
        self,
        payload: Any = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = ""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.HTTPError(f"http {self.status_code}")
            error.response = self
            raise error

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _group_http(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak.internal")
    monkeypatch.setattr(
        "m8flow_backend.integrations.auth.keycloak.groups.fetch_master_admin_token",
        lambda: "admin-token",
    )
    monkeypatch.setattr(
        "m8flow_backend.integrations.auth.keycloak.tenants.fetch_master_admin_token",
        lambda: "admin-token",
    )
    monkeypatch.setattr(
        "m8flow_backend.integrations.auth.keycloak.directory.fetch_master_admin_token",
        lambda: "admin-token",
    )


def _acme() -> dict[str, Any]:
    return {"id": "org-1", "alias": "acme", "name": "Acme"}


def _administrators() -> dict[str, Any]:
    return {"id": "g-admin", "name": "Administrators", "path": "/Administrators"}


def _ada() -> dict[str, Any]:
    return {"id": "u1", "username": "ada", "email": "ada@example.com"}


def test_tenant_roles_for_organization_group_hides_keycloak_names():
    assert tenant_roles_for_organization_group("Administrators") == ("tenant-admin",)
    assert tenant_roles_for_organization_group("Designers") == ("editor",)
    assert tenant_roles_for_organization_group("/editor") == ("editor",)
    assert tenant_roles_for_organization_group("unknown") == ()


def test_list_groups_returns_neutral_groups(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        if url == f"{ORGS_URL}/org-1":
            return _FakeResponse(_acme())
        if url == GROUPS_URL:
            return _FakeResponse([_administrators()])
        raise AssertionError(url)

    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.tenants.requests.get", fake_get)
    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.groups.requests.get", fake_get)
    found = KeycloakAuthProvider().directory_admin.list_groups(TenantRef(id="org-1"))
    assert found == [Group(identifier="Administrators", tenant_ref=TenantRef(id="org-1", alias="acme", name="Acme"))]


def test_create_group_posts_then_returns_neutral_group(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        assert url == GROUPS_URL
        assert json == {"name": "Reviewers"}
        return _FakeResponse({}, status_code=201, headers={"Location": f"{GROUPS_URL}/g-rev"})

    def fake_get(url, params=None, headers=None, timeout=None):
        if url == f"{ORGS_URL}/org-1":
            return _FakeResponse(_acme())
        if url == f"{GROUPS_URL}/g-rev":
            return _FakeResponse({"id": "g-rev", "name": "Reviewers", "path": "/Reviewers"})
        raise AssertionError(url)

    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.tenants.requests.get", fake_get)
    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.groups.requests.get", fake_get)
    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.groups.requests.post", fake_post)
    group = KeycloakAuthProvider().directory_admin.create_group(
        TenantRef(id="org-1"),
        identifier="Reviewers",
    )
    assert group.identifier == "Reviewers"
    assert group.tenant_ref is not None
    assert group.tenant_ref.id == "org-1"


def test_assign_roles_adds_member_to_mapped_group(monkeypatch):
    put_urls: list[str] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        if url == f"{ORGS_URL}/org-1":
            return _FakeResponse(_acme())
        if url == USERS_URL:
            return _FakeResponse([_ada()])
        if url == GROUPS_URL:
            return _FakeResponse([_administrators()])
        raise AssertionError(url)

    def fake_put(url, json=None, headers=None, timeout=None):
        put_urls.append(url)
        return _FakeResponse({}, status_code=204)

    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.tenants.requests.get", fake_get)
    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.directory.requests.get", fake_get)
    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.groups.requests.get", fake_get)
    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.groups.requests.put", fake_put)
    membership = KeycloakAuthProvider().directory_admin.assign_roles(
        username="ada",
        tenant_ref=TenantRef(id="org-1"),
        roles=["tenant-admin"],
    )
    assert membership.roles == ["tenant-admin"]
    assert put_urls == [f"{GROUPS_URL}/g-admin/members/u1"]


def test_ensure_default_groups_creates_missing_group(monkeypatch):
    posted: list[str] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        if url == f"{ORGS_URL}/org-1":
            return _FakeResponse(_acme())
        if url == GROUPS_URL:
            return _FakeResponse([])
        if url.startswith(f"{GROUPS_URL}/"):
            return _FakeResponse({"id": "g-new", "name": params and "x", "path": "/x"}, status_code=404)
        raise AssertionError(url)

    def fake_post(url, json=None, headers=None, timeout=None):
        posted.append(json["name"])
        return _FakeResponse(
            {},
            status_code=201,
            headers={"Location": f"{GROUPS_URL}/g-{json['name']}"},
        )

    def fake_get_groups(url, params=None, headers=None, timeout=None):
        if url == GROUPS_URL and params and params.get("search"):
            return _FakeResponse([])
        if url == GROUPS_URL:
            return _FakeResponse([{"id": f"g-{name}", "name": name, "path": f"/{name}"} for name in posted])
        if url.startswith(f"{GROUPS_URL}/g-"):
            name = url.rsplit("/", 1)[-1].removeprefix("g-")
            return _FakeResponse({"id": f"g-{name}", "name": name, "path": f"/{name}"})
        if url == f"{ORGS_URL}/org-1":
            return _FakeResponse(_acme())
        raise AssertionError(url)

    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.tenants.requests.get", fake_get_groups)
    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.groups.requests.get", fake_get_groups)
    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.groups.requests.post", fake_post)
    monkeypatch.setattr(
        "m8flow_backend.integrations.auth.keycloak.groups.default_group_identifiers",
        lambda: ("Administrators",),
    )
    monkeypatch.setattr(
        "m8flow_backend.integrations.auth.keycloak.groups.ensure_group_role_mappings",
        lambda *args, **kwargs: None,
    )
    created = KeycloakAuthProvider().directory_admin.ensure_default_groups(TenantRef(id="org-1"))
    assert posted == ["Administrators"]
    assert [group.identifier for group in created] == ["Administrators"]


def test_list_groups_http_error_is_provider_unavailable(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        if url == f"{ORGS_URL}/org-1":
            return _FakeResponse(_acme())
        return _FakeResponse({"error": "down"}, status_code=503)

    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.tenants.requests.get", fake_get)
    monkeypatch.setattr("m8flow_backend.integrations.auth.keycloak.groups.requests.get", fake_get)
    with pytest.raises(ProviderUnavailable):
        KeycloakAuthProvider().directory_admin.list_groups(TenantRef(id="org-1"))
