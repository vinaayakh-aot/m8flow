"""
spiff-arena adapter — wraps spiffworkflow_backend types.

Requires spiffworkflow-backend to be installed (optional extra).
"""
from __future__ import annotations

from typing import Any


class SpiffArenaErrorFactory:
    """ApiErrorFactory that raises spiffworkflow_backend.exceptions.api_error.ApiError."""

    def __call__(self, error_code: str, message: str, status_code: int) -> Exception:
        from spiffworkflow_backend.exceptions.api_error import ApiError
        return ApiError(error_code=error_code, message=message, status_code=status_code)


class SpiffArenaAuthzAdapter:
    """AuthorizationAdapter that delegates to spiffworkflow_backend.services.authorization_service."""

    def user_has_permission(self, user: Any, permission: str, target_uri: str) -> bool:
        from spiffworkflow_backend.services.authorization_service import AuthorizationService
        return AuthorizationService.user_has_permission(user, permission, target_uri)
