"""
Adapter registry for m8flow_core.

Configure once at startup:

    from m8flow_core.adapters.spiff_arena import SpiffArenaErrorFactory, SpiffArenaAuthzAdapter
    from m8flow_core.adapters import _registry
    _registry.configure(SpiffArenaErrorFactory(), SpiffArenaAuthzAdapter())
"""
from __future__ import annotations

from typing import Any


class _AdapterRegistry:
    def __init__(self):
        self._error_factory = None
        self._authz_adapter = None

    def configure(self, error_factory, authz_adapter=None) -> None:
        self._error_factory = error_factory
        self._authz_adapter = authz_adapter

    def get_error_factory(self):
        if self._error_factory is None:
            # Default to standalone (stdlib exceptions)
            from m8flow_core.adapters.standalone import StandaloneErrorFactory
            self._error_factory = StandaloneErrorFactory()
        return self._error_factory

    def get_authz_adapter(self):
        return self._authz_adapter


_registry = _AdapterRegistry()


def get_error_factory():
    return _registry.get_error_factory()


def get_authz_adapter() -> Any:
    return _registry.get_authz_adapter()
