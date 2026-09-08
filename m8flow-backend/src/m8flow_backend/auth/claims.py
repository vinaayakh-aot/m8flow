"""Pure JWT/decoded-token claim parsing -- organization membership, tenant
id/alias/name, and realm identity, all derived from a payload dict with no
DB or Flask `g` access of their own (tenant_id_from_payload and
active_organization_from_payload delegate to canonicalize.py for the one
thing pure parsing can't do: resolving a claimed identifier to the local
canonical tenant row).
"""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from m8flow_backend.auth.canonicalize import (
    _canonical_tenant_id_from_identifiers,
    current_tenant_identifiers,
)
from m8flow_backend.auth.tenant_context import TENANT_CLAIM

TENANT_ALIAS_CLAIM = "m8flow_tenant_alias"
TENANT_NAME_CLAIM = "m8flow_tenant_name"
REALM_NAME_CLAIM = "m8flow_realm_name"
AUTHENTICATION_IDENTIFIER_CLAIM = "m8flow_authentication_identifier"


def _string_claim(payload: Mapping[str, Any] | None, claim: str) -> str | None:
    if payload is None:
        return None
    value = payload.get(claim)
    if isinstance(value, str):
        value = value.strip()
        if value:
            return value
    return None


def organization_memberships_from_payload(
    payload: Mapping[str, Any] | None,
) -> list[tuple[str, Mapping[str, Any]]]:
    """Return normalized organization memberships from the built-in organization claim."""
    if payload is None:
        return []

    from m8flow_backend.integrations.auth.keycloak.claims import memberships_from_organization_claim

    memberships = memberships_from_organization_claim(dict(payload))
    normalized: list[tuple[str, Mapping[str, Any]]] = []
    for membership in memberships:
        alias = membership.tenant_ref.alias or membership.tenant_ref.id
        if not alias:
            continue
        normalized.append(
            (
                alias,
                {
                    "id": membership.tenant_ref.id,
                    "name": membership.tenant_ref.name,
                    "groups": membership.groups,
                },
            )
        )
    return normalized


def single_organization_from_payload(
    payload: Mapping[str, Any] | None,
) -> tuple[str, Mapping[str, Any]] | None:
    """Return the single organization entry from the built-in organization claim."""
    organizations = organization_memberships_from_payload(payload)
    if len(organizations) != 1:
        return None
    return organizations[0]


def active_organization_from_payload(
    payload: Mapping[str, Any] | None,
    tenant_id: str | None = None,
) -> tuple[str, Mapping[str, Any]] | None:
    """Return the active organization entry, or ``None`` when it cannot be resolved safely."""
    organizations = organization_memberships_from_payload(payload)
    if not organizations:
        return None

    if len(organizations) == 1:
        return organizations[0]

    tenant_identifiers = current_tenant_identifiers(tenant_id)
    if not tenant_identifiers:
        return None

    matching_organizations: list[tuple[str, Mapping[str, Any]]] = []
    for organization_alias, organization_details in organizations:
        organization_identifiers = {organization_alias}
        organization_id = organization_details.get("id")
        if isinstance(organization_id, str):
            normalized_organization_id = organization_id.strip()
            if normalized_organization_id:
                organization_identifiers.add(normalized_organization_id)
        else:
            normalized_organization_id = None

        canonical_tenant_id = _canonical_tenant_id_from_identifiers(
            normalized_organization_id,
            organization_alias,
        )
        if canonical_tenant_id:
            organization_identifiers.add(canonical_tenant_id)

        if organization_identifiers.intersection(tenant_identifiers):
            matching_organizations.append((organization_alias, organization_details))

    if len(matching_organizations) != 1:
        return None
    return matching_organizations[0]


def organization_group_identifiers_from_payload(
    payload: Mapping[str, Any] | None,
    tenant_id: str | None = None,
) -> list[str]:
    """Return normalized organization-local group identifiers for the active organization."""
    organization = active_organization_from_payload(payload, tenant_id=tenant_id)
    if organization is None:
        return []

    _organization_alias, organization_details = organization
    organization_groups = organization_details.get("groups")
    if not isinstance(organization_groups, list):
        return []

    normalized_group_identifiers: list[str] = []
    seen: set[str] = set()
    for organization_group in organization_groups:
        if not isinstance(organization_group, str):
            continue
        value = organization_group.strip()
        if not value:
            continue
        normalized_value = value.rstrip("/")
        if "/" in normalized_value:
            normalized_value = normalized_value.split("/")[-1].strip()
        if normalized_value and normalized_value not in seen:
            seen.add(normalized_value)
            normalized_group_identifiers.append(normalized_value)

    return normalized_group_identifiers


def tenant_id_from_payload(payload: Mapping[str, Any] | None) -> str | None:
    """Extract the configured tenant claim as the local canonical tenant id when possible."""
    organization = active_organization_from_payload(payload)
    if organization is not None:
        organization_alias, organization_details = organization
        organization_id = organization_details.get("id")
        if isinstance(organization_id, str):
            organization_id = organization_id.strip()
        else:
            organization_id = None

        canonical_organization_tenant_id = _canonical_tenant_id_from_identifiers(
            organization_id,
            organization_alias,
        )
        if canonical_organization_tenant_id:
            return canonical_organization_tenant_id
        if organization_id:
            return organization_id
        if organization_alias:
            return organization_alias

    explicit_tenant_id = _string_claim(payload, TENANT_CLAIM)
    if not explicit_tenant_id:
        return None

    canonical_explicit_tenant_id = _canonical_tenant_id_from_identifiers(
        explicit_tenant_id,
        _string_claim(payload, TENANT_ALIAS_CLAIM),
    )
    return canonical_explicit_tenant_id or explicit_tenant_id


def tenant_alias_from_payload(payload: Mapping[str, Any] | None) -> str | None:
    """Extract the active tenant alias from a decoded token payload."""
    tenant_alias = _string_claim(payload, TENANT_ALIAS_CLAIM)
    if tenant_alias:
        return tenant_alias

    organization = active_organization_from_payload(payload)
    if organization is None:
        return None
    organization_alias, _ = organization
    return organization_alias


def tenant_name_from_payload(payload: Mapping[str, Any] | None) -> str | None:
    """Extract the active tenant display name from a decoded token payload."""
    return _string_claim(payload, TENANT_NAME_CLAIM)


def realm_name_from_payload(payload: Mapping[str, Any] | None) -> str | None:
    """Extract the Keycloak realm name from a decoded token payload."""
    realm_name = _string_claim(payload, AUTHENTICATION_IDENTIFIER_CLAIM)
    if realm_name:
        return realm_name

    realm_name = _string_claim(payload, REALM_NAME_CLAIM)
    if realm_name:
        return realm_name

    realm_name = _string_claim(payload, "realm_name")
    if realm_name:
        return realm_name

    # Legacy RealmInfoMapper tokens used m8flow_tenant_name for the realm name.
    return _string_claim(payload, TENANT_NAME_CLAIM)


def authentication_identifier_from_payload(payload: Mapping[str, Any] | None) -> str | None:
    """Extract the auth-config identifier from a decoded token payload."""
    return realm_name_from_payload(payload)


def extract_realm_from_issuer(iss: str | None) -> str | None:
    """Extract the Keycloak realm name from an issuer URL."""
    if isinstance(iss, str) and "/realms/" in iss:
        return iss.split("/realms/")[-1].split("/")[0]
    return None


def realm_from_service(service: str | None) -> str:
    """Derive a stable tenant-like value from a service/issuer string."""
    realm = extract_realm_from_issuer(service)
    if realm:
        return realm
    if not service:
        return "unknown"
    normalized = service.rstrip("/")
    return normalized.replace("://", "_").replace("/", "_")[-32:] or "unknown"
