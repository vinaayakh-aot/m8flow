"""Auth0 identity provider adapter (stub — not yet implemented).

To implement:
1. Install auth0-python or use the Auth0 Management API directly.
2. Implement TenantProvisioner + TokenManager protocols from m8flow_core.auth.base.
3. Register at startup: m8flow_core.configure_auth_provider(Auth0IdentityProvider.from_env())
"""
from __future__ import annotations


class Auth0IdentityProvider:
    """Placeholder for a future Auth0 identity provider implementation."""

    @classmethod
    def from_env(cls) -> "Auth0IdentityProvider":
        raise NotImplementedError(
            "Auth0IdentityProvider is not yet implemented. "
            "See m8flow_core/auth/adapters/auth0.py for instructions."
        )
