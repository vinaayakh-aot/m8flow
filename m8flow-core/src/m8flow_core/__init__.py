"""
m8flow-core — portable domain library for m8flow.

Configure before importing models:

    import m8flow_core
    m8flow_core.configure_db(db, BaseModel)
    m8flow_core.configure_adapters(error_factory, authz_adapter)
    m8flow_core.configure_auth_provider(provider)
"""

from __future__ import annotations

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("m8flow-core")
except PackageNotFoundError:
    __version__ = "0.0.0"

from m8flow_core.db.registry import configure_db, get_db, get_base_model  # noqa: F401
from m8flow_core.exceptions import (  # noqa: F401
    M8flowError,
    M8flowConfigurationError,
    M8flowTenantContextError,
    M8flowNotFoundError,
    M8flowAuthorizationError,
)


def configure_adapters(error_factory, authz_adapter=None):
    """Configure the spiff-arena or standalone adapter for error handling and authorization."""
    from m8flow_core.adapters import _registry
    _registry.configure(error_factory=error_factory, authz_adapter=authz_adapter)


def configure_auth_provider(provider):
    """Configure the identity/auth provider (Keycloak, Auth0, etc.)."""
    from m8flow_core.auth.registry import _set_provider
    _set_provider(provider)


def get_auth_provider():
    """Return the configured auth provider."""
    from m8flow_core.auth.registry import get_provider
    return get_provider()


def configure_tenant_paths(prefixes: list[str]) -> None:
    """Override the default tenant-context-exempt path prefixes.

    Call during application startup to replace the built-in spiff-arena
    path list with paths appropriate for your deployment.
    """
    from m8flow_core.tenancy import configure_tenant_paths as _configure
    _configure(prefixes)
