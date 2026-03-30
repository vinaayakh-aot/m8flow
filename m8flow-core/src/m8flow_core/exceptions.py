"""
m8flow_core.exceptions — public exception hierarchy.

All exceptions raised by m8flow_core are subclasses of M8flowError so consumers
can write a single ``except m8flow_core.M8flowError`` catch-all without
accidentally swallowing unrelated ``RuntimeError`` / ``ValueError`` exceptions.
"""
from __future__ import annotations


class M8flowError(Exception):
    """Base class for all m8flow_core exceptions."""


class M8flowConfigurationError(M8flowError):
    """Raised when the library has not been configured before use.

    Typical cause: ``configure_db()`` was not called before importing models,
    or ``configure_adapters()`` was not called before calling services.
    """


class M8flowTenantContextError(M8flowError):
    """Raised when a tenant id is required but not present in the execution context.

    Typical cause: a request reached a tenant-aware endpoint without a valid
    ``m8flow_tenant_id`` in the JWT or request context.
    """


class M8flowNotFoundError(M8flowError):
    """Raised when a requested resource does not exist.

    Analogous to HTTP 404. Raised by services like TenantService and
    TemplateService when a lookup returns no result.
    """


class M8flowAuthorizationError(M8flowError):
    """Raised when the current user lacks permission for an operation.

    Analogous to HTTP 403.
    """
