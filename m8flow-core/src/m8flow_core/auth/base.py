"""
Provider-agnostic protocols for identity/auth systems.

Implement these protocols to support a new auth provider (Keycloak, Auth0, etc.).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from m8flow_core.auth.models import AuthToken, AuthUser, TenantRealm


@runtime_checkable
class TenantProvisioner(Protocol):
    """Provision and manage identity resources for a tenant."""

    def provision_tenant(self, tenant: TenantRealm) -> None:
        """Create all necessary identity provider resources for a new tenant."""
        ...

    def deprovision_tenant(self, tenant_id: str) -> None:
        """Remove identity provider resources for a tenant."""
        ...

    def create_user(self, tenant_id: str, user: AuthUser) -> AuthUser:
        """Create a user within the given tenant's realm/organization."""
        ...

    def get_login_url(self, tenant_id: str, redirect_uri: str) -> str:
        """Return the login URL for the given tenant."""
        ...


@runtime_checkable
class TokenManager(Protocol):
    """Validate and decode bearer tokens."""

    def validate_token(self, token: str, tenant_id: str) -> AuthToken:
        """Validate and decode a bearer token for the given tenant.

        Raises:
            Exception: If the token is invalid or expired.
        """
        ...

    def get_discovery_url(self, tenant_id: str) -> str:
        """Return the OIDC discovery URL for the given tenant."""
        ...


@runtime_checkable
class IdentityProvider(Protocol):
    """Combined interface for a full identity provider."""

    def provision_tenant(self, tenant: TenantRealm) -> None: ...
    def deprovision_tenant(self, tenant_id: str) -> None: ...
    def create_user(self, tenant_id: str, user: AuthUser) -> AuthUser: ...
    def get_login_url(self, tenant_id: str, redirect_uri: str) -> str: ...
    def validate_token(self, token: str, tenant_id: str) -> AuthToken: ...
    def get_discovery_url(self, tenant_id: str) -> str: ...
