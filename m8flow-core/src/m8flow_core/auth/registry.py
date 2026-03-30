"""
Auth provider registry.

Configure once at startup:

    from m8flow_core.auth.adapters.keycloak import KeycloakIdentityProvider
    import m8flow_core
    m8flow_core.configure_auth_provider(KeycloakIdentityProvider.from_env())
"""
from __future__ import annotations

from typing import Any

_provider: Any = None


def _set_provider(provider: Any) -> None:
    global _provider
    _provider = provider


def get_provider() -> Any:
    if _provider is None:
        raise RuntimeError(
            "m8flow_core auth provider is not configured. "
            "Call m8flow_core.configure_auth_provider(provider) at startup."
        )
    return _provider
