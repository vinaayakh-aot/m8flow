"""Shim: tenant-role helpers live on the auth seam.

The Keycloak group-name table is in ``integrations.auth.keycloak.role_mapping``.
Neutral role names are in ``integrations.auth.base.roles``.
"""
from __future__ import annotations

from m8flow_backend.integrations.auth.base.roles import VALID_TENANT_ROLE_NAMES
from m8flow_backend.integrations.auth.keycloak.role_mapping import (
    ORGANIZATION_GROUP_FOR_TENANT_ROLE as DEFAULT_TENANT_ROLE_TO_ORGANIZATION_GROUP,
    ORGANIZATION_GROUP_ROLE_MAPPING_CONFIGURED_ATTRIBUTE,
    ORGANIZATION_GROUP_ROLE_NAMES_ATTRIBUTE,
    TENANT_ROLE_FOR_ORGANIZATION_GROUP as DEFAULT_ORGANIZATION_GROUP_TO_TENANT_ROLE,
    normalize_tenant_role_name,
    normalize_tenant_role_names,
    organization_group_name_candidates_for_tenant_role,
    primary_organization_group_name_for_tenant_role,
    tenant_roles_for_organization_group,
)

__all__ = [
    "DEFAULT_ORGANIZATION_GROUP_TO_TENANT_ROLE",
    "DEFAULT_TENANT_ROLE_TO_ORGANIZATION_GROUP",
    "ORGANIZATION_GROUP_ROLE_MAPPING_CONFIGURED_ATTRIBUTE",
    "ORGANIZATION_GROUP_ROLE_NAMES_ATTRIBUTE",
    "VALID_TENANT_ROLE_NAMES",
    "normalize_tenant_role_name",
    "normalize_tenant_role_names",
    "organization_group_name_candidates_for_tenant_role",
    "primary_organization_group_name_for_tenant_role",
    "tenant_roles_for_organization_group",
]
