"""Canonical neutral role vocabulary for m8flow RBAC.

This is m8flow's own, provider-independent vocabulary. A provider translates
between these names and its realization of them (Keycloak: organization groups
named ``Administrators``/``Designers``/... plus realm roles).

The Keycloak group-name table lives in ``integrations.auth.keycloak.role_mapping``.
``services.tenant_group_mapping`` re-exports these names for older callers.
"""
from __future__ import annotations

VALID_TENANT_ROLE_NAMES = frozenset(
    (
        "tenant-admin",
        "editor",
        "integrator",
        "reviewer",
        "submitter",
        "viewer",
    )
)

# The global, non-tenant-scoped role that grants platform super-admin.
SUPER_ADMIN_ROLE = "super-admin"
