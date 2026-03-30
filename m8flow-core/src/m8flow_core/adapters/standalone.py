"""
Standalone adapter — works without spiff-arena installed.

Uses standard Python exceptions wrapped with HTTP status information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class M8flowApiError(Exception):
    """Stdlib-based API error carrying an HTTP status code."""
    error_code: str
    message: str
    status_code: int

    def __str__(self) -> str:
        return f"[{self.status_code}] {self.error_code}: {self.message}"


class StandaloneErrorFactory:
    """ApiErrorFactory implementation using M8flowApiError."""

    def __call__(self, error_code: str, message: str, status_code: int) -> Exception:
        return M8flowApiError(error_code=error_code, message=message, status_code=status_code)


class StandaloneAuthzAdapter:
    """AuthorizationAdapter that grants all permissions (for development/testing)."""

    def user_has_permission(self, user: Any, permission: str, target_uri: str) -> bool:
        return True
