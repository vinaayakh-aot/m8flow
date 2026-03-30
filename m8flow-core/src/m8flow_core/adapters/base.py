"""
Base protocols for m8flow_core adapters.

These protocols define the interfaces that concrete adapters must implement,
allowing m8flow_core to work with spiff-arena, standalone, or other backends.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ApiErrorFactory(Protocol):
    """Factory that creates HTTP-aware error exceptions."""

    def __call__(self, error_code: str, message: str, status_code: int) -> Exception:
        """Create an API error exception.

        Args:
            error_code: Machine-readable error code (e.g. "not_found").
            message: Human-readable error message.
            status_code: HTTP status code (e.g. 404, 400).

        Returns:
            An exception instance ready to be raised.
        """
        ...


@runtime_checkable
class UserProtocol(Protocol):
    """Minimal interface for a user object."""
    username: str


@runtime_checkable
class AuthorizationAdapter(Protocol):
    """Permission checking interface."""

    def user_has_permission(self, user: Any, permission: str, target_uri: str) -> bool:
        """Return True if user has the given permission on target_uri."""
        ...
