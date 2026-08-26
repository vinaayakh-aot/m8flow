"""Keycloak organization-group name ↔ neutral tenant role.

``verify_token`` uses this so VerifiedClaims never leak Keycloak group names
like ``Administrators``. Stored group names still appear in the HTTP directory
API because that is the existing client contract.
"""
from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType

from m8flow_backend.integrations.auth.base.roles import VALID_TENANT_ROLE_NAMES

ORGANIZATION_GROUP_FOR_TENANT_ROLE = MappingProxyType(
    {
        "tenant-admin": "Administrators",
        "editor": "Designers",
        "integrator": "Support",
        "reviewer": "Approvers",
        "submitter": "Submitters",
        "viewer": "Viewers",
    }
)

TENANT_ROLE_FOR_ORGANIZATION_GROUP = MappingProxyType(
    {group: role for role, group in ORGANIZATION_GROUP_FOR_TENANT_ROLE.items()}
)

ORGANIZATION_GROUP_ROLE_NAMES_ATTRIBUTE = "m8flow_role_names"
ORGANIZATION_GROUP_ROLE_MAPPING_CONFIGURED_ATTRIBUTE = "m8flow_role_mapping_configured"


def normalize_tenant_role_name(role_name: str | None) -> str:
    normalized = str(role_name or "").strip()
    if normalized not in VALID_TENANT_ROLE_NAMES:
        return ""
    return normalized


def normalize_tenant_role_names(role_names: Iterable[str | None] | None) -> tuple[str, ...]:
    normalized_role_names: list[str] = []
    seen: set[str] = set()
    for role_name in role_names or ():
        normalized = normalize_tenant_role_name(role_name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_role_names.append(normalized)
    return tuple(sorted(normalized_role_names))


def organization_group_name_candidates_for_tenant_role(role_name: str | None) -> tuple[str, ...]:
    normalized = normalize_tenant_role_name(role_name)
    if not normalized:
        return ()
    candidates: list[str] = []
    mapped = ORGANIZATION_GROUP_FOR_TENANT_ROLE.get(normalized)
    if mapped:
        candidates.append(mapped)
    if normalized not in candidates:
        candidates.append(normalized)
    return tuple(candidates)


def primary_organization_group_name_for_tenant_role(role_name: str | None) -> str:
    candidates = organization_group_name_candidates_for_tenant_role(role_name)
    return candidates[0] if candidates else ""


def tenant_roles_for_organization_group(group_name: str | None) -> tuple[str, ...]:
    normalized = str(group_name or "").strip().strip("/")
    if not normalized:
        return ()
    if "/" in normalized:
        normalized = normalized.split("/")[-1].strip()
    mapped = TENANT_ROLE_FOR_ORGANIZATION_GROUP.get(normalized)
    if mapped:
        return (mapped,)
    if normalized in VALID_TENANT_ROLE_NAMES:
        return (normalized,)
    return ()
