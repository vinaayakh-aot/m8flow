"""Keycloak-specific environment accessors.

Env keys (``M8FLOW_KEYCLOAK_*`` / legacy ``KEYCLOAK_*``) are unchanged.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_KEYCLOAK_CLIENT_SECRET = "JXeQExm0JhQPLumgHtIIqf52bDalHz0q"
DEFAULT_SHARED_REALM_NAME = "m8flow"
DEFAULT_MASTER_REALM_NAME = "master"

# integrations/auth/keycloak/config.py -> m8flow_backend/
_M8FLOW_BACKEND_PACKAGE_DIR = Path(__file__).resolve().parents[3]


def _get(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key)
    if value is not None and value != "":
        return value.strip()
    return default


def keycloak_url() -> str:
    """Keycloak base URL (no trailing slash)."""
    url = _get("KEYCLOAK_URL") or _get("M8FLOW_KEYCLOAK_URL") or "http://localhost:6842"
    return url.rstrip("/")


def keycloak_public_issuer_base() -> str:
    """Base URL Keycloak uses for the iss claim in tokens (same as KC_HOSTNAME).
    When this differs from keycloak_url() (e.g. Docker proxy), set KEYCLOAK_HOSTNAME or
    M8FLOW_KEYCLOAK_PUBLIC_ISSUER_BASE so the backend accepts the token issuer."""
    url = _get("KEYCLOAK_HOSTNAME") or _get("M8FLOW_KEYCLOAK_PUBLIC_ISSUER_BASE") or keycloak_url()
    return url.rstrip("/")


def keycloak_admin_user() -> str:
    """Master realm admin username (default is created by Keycloak entrypoint)."""
    return _get("KEYCLOAK_ADMIN_USER") or _get("M8FLOW_KEYCLOAK_ADMIN_USER")


def keycloak_admin_password() -> str:
    """Master realm admin password (from env only)."""
    return _get("KEYCLOAK_ADMIN_PASSWORD") or _get("M8FLOW_KEYCLOAK_ADMIN_PASSWORD") or ""


def shared_realm_name() -> str:
    """Shared tenant-user realm name."""
    return _get("M8FLOW_KEYCLOAK_SHARED_REALM") or DEFAULT_SHARED_REALM_NAME


def shared_realm_label() -> str:
    """Display label for the shared realm auth option."""
    realm_name = shared_realm_name()
    if realm_name == DEFAULT_SHARED_REALM_NAME:
        return "M8Flow Realm"
    return realm_name


def default_organization_alias() -> str:
    """Alias for the default shared-realm organization."""
    return _get("M8FLOW_KEYCLOAK_DEFAULT_ORGANIZATION_ALIAS") or shared_realm_name()


def default_organization_name() -> str:
    """Display name for the default shared-realm organization."""
    return _get("M8FLOW_KEYCLOAK_DEFAULT_ORGANIZATION_NAME") or default_organization_alias()


def master_realm_name() -> str:
    """Platform/bootstrap admin realm name."""
    return _get("M8FLOW_KEYCLOAK_MASTER_REALM") or DEFAULT_MASTER_REALM_NAME


def realm_template_path() -> str:
    """Path to realm template JSON (absolute, or relative to cwd, or default next to package)."""
    raw = _get("M8FLOW_KEYCLOAK_REALM_TEMPLATE_PATH")
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = Path.cwd() / raw
        return str(p)
    # Same walk as the former config.py location: m8flow_backend -> src -> m8flow-backend
    root = _M8FLOW_BACKEND_PACKAGE_DIR.parent.parent
    default = root / "keycloak" / "realm_exports" / "m8flow-tenant-template.json"
    return str(default)


def keycloak_default_groups_path() -> str:
    """Path to the repo-owned default Keycloak organizational groups config."""
    raw = _get("M8FLOW_KEYCLOAK_DEFAULT_GROUPS_PATH")
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = Path.cwd() / raw
        return str(p)

    default = _M8FLOW_BACKEND_PACKAGE_DIR / "config" / "keycloak" / "default_groups.json"
    return str(default)


def spoke_keystore_p12_path() -> str | None:
    """Path to PKCS#12 keystore for spoke realm client auth."""
    default = "m8flow-backend/keystore.p12"
    raw = _get("M8FLOW_KEYCLOAK_SPOKE_KEYSTORE_P12") or default
    p = Path(raw)
    if not p.is_absolute():
        p = Path.cwd() / raw
    return str(p) if p.exists() else None


def spoke_keystore_password() -> str:
    """Password for spoke keystore (from env only)."""
    return _get("M8FLOW_KEYCLOAK_SPOKE_KEYSTORE_PASSWORD") or ""


def spoke_client_id() -> str:
    """Client id used in each spoke realm for token/login."""
    return _get("M8FLOW_KEYCLOAK_SPOKE_CLIENT_ID") or "m8flow-backend"


def spoke_client_secret() -> str:
    """Client secret for spoke realm client (from env only). Set M8FLOW_KEYCLOAK_SPOKE_CLIENT_SECRET when using client-secret auth."""
    return _get("M8FLOW_KEYCLOAK_SPOKE_CLIENT_SECRET") or ""


def master_client_secret() -> str:
    """Client secret for master realm browser login."""
    return (
        _get("M8FLOW_KEYCLOAK_MASTER_CLIENT_SECRET")
        or spoke_client_secret()
        or DEFAULT_KEYCLOAK_CLIENT_SECRET
    )


def template_realm_name() -> str:
    """Realm name in the template (for substitution)."""
    return DEFAULT_SHARED_REALM_NAME
