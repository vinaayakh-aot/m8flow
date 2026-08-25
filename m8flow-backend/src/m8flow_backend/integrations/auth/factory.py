"""Resolve the active ``AuthProvider`` from configuration.

Selection key: ``M8FLOW_AUTH_PROVIDER`` (default ``keycloak``). A second
implementation registers with ``register_auth_provider``; call sites keep
using ``get_auth_provider()``.

The process holds one instance (lazy singleton). Request-time code and
non-request bootstrap both need the provider, and today's Keycloak access is
already process-global env-driven functions — a Flask app-context accessor
would force an app context on paths that don't have one. Tests call
``reset_auth_provider()``.
"""
from __future__ import annotations

import os
import threading
from collections.abc import Callable

from m8flow_backend.integrations.auth.base.errors import AuthProviderError
from m8flow_backend.integrations.auth.base.provider import AuthProvider

AUTH_PROVIDER_ENV = "M8FLOW_AUTH_PROVIDER"
DEFAULT_AUTH_PROVIDER = "keycloak"

_registry: dict[str, Callable[[], AuthProvider]] = {}
_instance: AuthProvider | None = None
_lock = threading.Lock()
_builtins_registered = False


def register_auth_provider(name: str, factory: Callable[[], AuthProvider]) -> None:
    """Register (or replace) a provider factory under ``name``."""
    key = name.strip().lower()
    if not key:
        raise AuthProviderError("Auth provider name must be non-empty")
    _registry[key] = factory


def reset_auth_provider() -> None:
    """Drop the cached instance so the next ``get_auth_provider()`` rebuilds it."""
    global _instance
    with _lock:
        _instance = None


def get_auth_provider() -> AuthProvider:
    """Return the process-wide active provider, creating it on first use."""
    global _instance
    if _instance is not None:
        return _instance
    with _lock:
        if _instance is None:
            _instance = _build_auth_provider()
        return _instance


def _ensure_builtins() -> None:
    global _builtins_registered
    if _builtins_registered:
        return
    from m8flow_backend.integrations.auth.keycloak.provider import KeycloakAuthProvider

    register_auth_provider(DEFAULT_AUTH_PROVIDER, KeycloakAuthProvider)
    _builtins_registered = True


def _build_auth_provider() -> AuthProvider:
    _ensure_builtins()
    raw = os.environ.get(AUTH_PROVIDER_ENV)
    name = (raw.strip() if raw else "") or DEFAULT_AUTH_PROVIDER
    key = name.lower()
    factory = _registry.get(key)
    if factory is None:
        known = ", ".join(sorted(_registry)) or "(none)"
        raise AuthProviderError(f"Unknown auth provider {name!r}. Registered: {known}")
    return factory()
