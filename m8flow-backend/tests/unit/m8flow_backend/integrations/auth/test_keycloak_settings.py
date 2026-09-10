from __future__ import annotations

from pathlib import Path

import pytest

import m8flow_backend
from m8flow_backend import config
from m8flow_backend.integrations.auth.keycloak import settings as keycloak_settings


@pytest.fixture(autouse=True)
def _reset_settings():
    keycloak_settings.reset_keycloak_settings()
    yield
    keycloak_settings.reset_keycloak_settings()


def test_keycloak_config_reads_env(monkeypatch):
    monkeypatch.setenv("M8FLOW_KEYCLOAK_URL", "http://keycloak.test:9999")
    monkeypatch.setenv("M8FLOW_KEYCLOAK_SHARED_REALM", "shared-test")
    assert keycloak_settings.keycloak_url() == "http://keycloak.test:9999"
    assert keycloak_settings.shared_realm_name() == "shared-test"
    assert keycloak_settings.spoke_client_id()


def test_host_config_no_longer_reexports_keycloak_accessors():
    assert not hasattr(config, "keycloak_url")
    assert not hasattr(config, "shared_realm_name")
    assert not hasattr(config, "spoke_client_id")


def test_default_groups_path_stays_on_the_m8flow_backend_package():
    package_dir = Path(m8flow_backend.__file__).resolve().parent
    expected = package_dir / "config" / "keycloak" / "default_groups.json"
    assert Path(keycloak_settings.keycloak_default_groups_path()) == expected


def test_realm_template_default_walk_matches_former_config_location():
    package_dir = Path(m8flow_backend.__file__).resolve().parent
    expected = package_dir.parent.parent / "keycloak" / "realm_exports" / "m8flow-tenant-template.json"
    assert Path(keycloak_settings.realm_template_path()) == expected
