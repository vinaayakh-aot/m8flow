"""Keycloak organization-group Admin API as neutral groups + role mapping.

The provider returns Group / User / Membership.
"""
from __future__ import annotations

import copy
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable, UserNotFound
from m8flow_backend.integrations.auth.base.models import Group, TenantRef, User
from m8flow_backend.integrations.auth.keycloak.client_auth import fetch_master_admin_token
from m8flow_backend.integrations.auth.keycloak.config import (
    keycloak_default_groups_path,
    keycloak_url,
    shared_realm_name,
)
from m8flow_backend.integrations.auth.keycloak.directory import fetch_user_representation, user_from_representation
from m8flow_backend.integrations.auth.keycloak.role_mapping import (
    ORGANIZATION_GROUP_FOR_TENANT_ROLE,
    ORGANIZATION_GROUP_ROLE_MAPPING_CONFIGURED_ATTRIBUTE,
    ORGANIZATION_GROUP_ROLE_NAMES_ATTRIBUTE,
    normalize_tenant_role_names,
    primary_organization_group_name_for_tenant_role,
    tenant_roles_for_organization_group,
)
from m8flow_backend.integrations.auth.keycloak.tenants import resolve_tenant_ref

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 30
_FALLBACK_DEFAULT_GROUP_NAMES = tuple(ORGANIZATION_GROUP_FOR_TENANT_ROLE.values())


def group_from_representation(payload: dict[str, Any], tenant_ref: TenantRef) -> Group:
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProviderUnavailable("Directory group is missing an identifier")
    return Group(identifier=name.strip(), tenant_ref=tenant_ref)


def _admin_token(admin_token: str | None) -> str:
    return admin_token or fetch_master_admin_token()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _groups_url(organization_id: str, *segments: str) -> str:
    base = f"{keycloak_url()}/admin/realms/{shared_realm_name()}/organizations/{quote(organization_id, safe='')}/groups"
    extra = [quote(segment.strip("/"), safe="") for segment in segments if segment and str(segment).strip("/")]
    if not extra:
        return base
    return f"{base}/{'/'.join(extra)}"


def _member_groups_url(organization_id: str, member_id: str) -> str:
    return (
        f"{keycloak_url()}/admin/realms/{shared_realm_name()}/organizations/"
        f"{quote(organization_id, safe='')}/members/{quote(member_id, safe='')}/groups"
    )


def _role_mappings_url(organization_id: str, group_id: str, *segments: str) -> str:
    base = _groups_url(organization_id, group_id, "role-mappings", "realm")
    extra = [quote(segment.strip("/"), safe="") for segment in segments if segment and str(segment).strip("/")]
    if not extra:
        return base
    return f"{base}/{'/'.join(extra)}"


def _unavailable(action: str, exc: Exception) -> ProviderUnavailable:
    error = ProviderUnavailable(f"Could not {action}")
    error.__cause__ = exc
    return error


def default_group_identifiers() -> tuple[str, ...]:
    """Top-level organization group names seeded for a new tenant."""
    try:
        config_path = Path(keycloak_default_groups_path())
        with open(config_path, encoding="utf-8") as config_file:
            config_data = json.load(config_file)
        raw_paths = config_data.get("groups") if isinstance(config_data, dict) else config_data
        if not isinstance(raw_paths, list):
            return _FALLBACK_DEFAULT_GROUP_NAMES
        names: list[str] = []
        seen: set[str] = set()
        for item in raw_paths:
            if not isinstance(item, str):
                continue
            name = item.strip().strip("/").split("/")[-1].strip()
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)
        return tuple(names) if names else _FALLBACK_DEFAULT_GROUP_NAMES
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Falling back to built-in organization role groups: %s", exc)
        return _FALLBACK_DEFAULT_GROUP_NAMES


def _organization_id(tenant_ref: TenantRef, *, admin_token: str | None = None) -> str:
    tenant = resolve_tenant_ref(tenant_ref, admin_token=admin_token)
    tenant_id = tenant.ref.id
    if not tenant_id:
        raise ProviderUnavailable("Directory tenant is missing an id")
    return tenant_id


def _group_identifier(group: Group) -> str:
    identifier = str(group.identifier or "").strip()
    if not identifier:
        raise ValueError("group identifier is required")
    return identifier


def list_group_representations(
    organization_id: str,
    *,
    admin_token: str | None = None,
    brief_representation: bool = True,
) -> list[dict[str, Any]]:
    if not organization_id or not str(organization_id).strip():
        raise ValueError("organization_id is required")
    normalized_id = str(organization_id).strip()
    try:
        response = requests.get(
            _groups_url(normalized_id),
            params={
                "briefRepresentation": "true" if brief_representation else "false",
                "populateHierarchy": "false",
                "subGroupsCount": "false",
                "max": 100,
            },
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise _unavailable(f"list groups for tenant {normalized_id!r}", exc)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def fetch_group_representation_by_id(
    organization_id: str,
    group_id: str,
    *,
    admin_token: str | None = None,
) -> dict[str, Any] | None:
    if not organization_id or not str(organization_id).strip():
        raise ValueError("organization_id is required")
    if not group_id or not str(group_id).strip():
        raise ValueError("group_id is required")
    normalized_org = str(organization_id).strip()
    normalized_group_id = str(group_id).strip()
    try:
        response = requests.get(
            _groups_url(normalized_org, normalized_group_id),
            params={"subGroupsCount": "false"},
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise _unavailable(f"fetch group {normalized_group_id!r}", exc)
    return payload if isinstance(payload, dict) else None


def fetch_group_representation_by_name(
    organization_id: str,
    group_name: str,
    *,
    admin_token: str | None = None,
) -> dict[str, Any] | None:
    if not organization_id or not str(organization_id).strip():
        raise ValueError("organization_id is required")
    if not group_name or not str(group_name).strip():
        raise ValueError("group_name is required")
    normalized_org = str(organization_id).strip()
    normalized_name = str(group_name).strip()
    try:
        response = requests.get(
            _groups_url(normalized_org),
            params={
                "search": normalized_name,
                "exact": "true",
                "briefRepresentation": "true",
                "populateHierarchy": "false",
                "subGroupsCount": "false",
                "max": 100,
            },
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise _unavailable(f"look up group {normalized_name!r}", exc)
    if not isinstance(payload, list):
        return None
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("name") != normalized_name:
            continue
        path = item.get("path")
        if path in {None, normalized_name, f"/{normalized_name}"}:
            return item
    return None


def fetch_member_group_representations(
    organization_id: str,
    member_id: str,
    *,
    admin_token: str | None = None,
) -> list[dict[str, Any]]:
    if not organization_id or not str(organization_id).strip():
        raise ValueError("organization_id is required")
    if not member_id or not str(member_id).strip():
        raise ValueError("member_id is required")
    normalized_org = str(organization_id).strip()
    normalized_member = str(member_id).strip()
    try:
        response = requests.get(
            _member_groups_url(normalized_org, normalized_member),
            params={"briefRepresentation": "true", "max": 100},
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise _unavailable(f"list groups for member {normalized_member!r}", exc)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def list_group_member_representations(
    organization_id: str,
    group_id: str,
    *,
    admin_token: str | None = None,
) -> list[dict[str, Any]]:
    if not organization_id or not str(organization_id).strip():
        raise ValueError("organization_id is required")
    if not group_id or not str(group_id).strip():
        raise ValueError("group_id is required")
    normalized_org = str(organization_id).strip()
    normalized_group_id = str(group_id).strip()
    try:
        response = requests.get(
            _groups_url(normalized_org, normalized_group_id, "members"),
            params={"briefRepresentation": "true", "max": 100},
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise _unavailable(f"list members of group {normalized_group_id!r}", exc)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def create_group_representation(
    organization_id: str,
    group_name: str,
    *,
    admin_token: str | None = None,
) -> dict[str, Any]:
    if not organization_id or not str(organization_id).strip():
        raise ValueError("organization_id is required")
    if not group_name or not str(group_name).strip():
        raise ValueError("group_name is required")
    normalized_org = str(organization_id).strip()
    normalized_name = str(group_name).strip()
    token = _admin_token(admin_token)
    try:
        response = requests.post(
            _groups_url(normalized_org),
            json={"name": normalized_name},
            headers=_headers(token),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise _unavailable(f"create group {normalized_name!r}", exc)
    location = (response.headers or {}).get("Location")
    representation: dict[str, Any] | None = None
    if location and isinstance(location, str):
        group_id = location.strip().rstrip("/").split("/")[-1]
        representation = fetch_group_representation_by_id(normalized_org, group_id, admin_token=token)
    if representation is None:
        representation = fetch_group_representation_by_name(normalized_org, normalized_name, admin_token=token)
    if representation is None:
        raise ProviderUnavailable(
            f"Group {normalized_name!r} was created in tenant {normalized_org!r} but could not be fetched"
        )
    return representation


def delete_group_representation(
    organization_id: str,
    group_id: str,
    *,
    admin_token: str | None = None,
) -> None:
    if not organization_id or not str(organization_id).strip():
        raise ValueError("organization_id is required")
    if not group_id or not str(group_id).strip():
        raise ValueError("group_id is required")
    normalized_org = str(organization_id).strip()
    normalized_group_id = str(group_id).strip()
    try:
        response = requests.delete(
            _groups_url(normalized_org, normalized_group_id),
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code != 404:
            response.raise_for_status()
    except requests.RequestException as exc:
        raise _unavailable(f"delete group {normalized_group_id!r}", exc)


def _attribute_values(attributes: Mapping[str, Any] | None, attribute_name: str) -> tuple[str, ...]:
    if not isinstance(attributes, Mapping):
        return ()
    raw_value = attributes.get(attribute_name)
    if isinstance(raw_value, str):
        raw_values = [raw_value]
    elif isinstance(raw_value, list):
        raw_values = [value for value in raw_value if isinstance(value, str)]
    else:
        return ()
    normalized_values: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_values:
        for candidate in raw_item.split(","):
            normalized = candidate.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            normalized_values.append(normalized)
    return tuple(normalized_values)


def _attribute_enabled(attributes: Mapping[str, Any] | None, attribute_name: str) -> bool:
    values = {value.casefold() for value in _attribute_values(attributes, attribute_name)}
    return any(value in {"1", "true", "yes", "on"} for value in values)


def role_names_from_representation(group: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(group, Mapping):
        return []
    group_name = group.get("name")
    attributes = group.get("attributes")
    mapping_attributes = attributes if isinstance(attributes, Mapping) else None
    if _attribute_enabled(mapping_attributes, ORGANIZATION_GROUP_ROLE_MAPPING_CONFIGURED_ATTRIBUTE):
        return list(
            normalize_tenant_role_names(
                _attribute_values(mapping_attributes, ORGANIZATION_GROUP_ROLE_NAMES_ATTRIBUTE)
            )
        )
    return list(tenant_roles_for_organization_group(str(group_name or "").strip()))


def _put_group_attributes(
    organization_id: str,
    group_id: str,
    representation: dict[str, Any],
    *,
    name: str | None = None,
    role_names: list[str] | tuple[str, ...] | None = None,
    admin_token: str | None = None,
) -> dict[str, Any]:
    token = _admin_token(admin_token)
    existing_attributes = representation.get("attributes")
    updated_attributes = copy.deepcopy(existing_attributes) if isinstance(existing_attributes, dict) else {}
    group_name = name.strip() if isinstance(name, str) and name.strip() else representation.get("name")
    if not isinstance(group_name, str) or not group_name.strip():
        raise ValueError(f"Group '{group_id}' in tenant '{organization_id}' does not have a valid name.")
    if role_names is not None:
        normalized_role_names = list(normalize_tenant_role_names(role_names))
        updated_attributes[ORGANIZATION_GROUP_ROLE_MAPPING_CONFIGURED_ATTRIBUTE] = ["true"]
        if normalized_role_names:
            updated_attributes[ORGANIZATION_GROUP_ROLE_NAMES_ATTRIBUTE] = normalized_role_names
        else:
            updated_attributes.pop(ORGANIZATION_GROUP_ROLE_NAMES_ATTRIBUTE, None)
    payload: dict[str, Any] = {"name": group_name.strip(), "attributes": updated_attributes}
    description = representation.get("description")
    if isinstance(description, str):
        payload["description"] = description
    try:
        response = requests.put(
            _groups_url(organization_id, group_id),
            json=payload,
            headers=_headers(token),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise _unavailable(f"update group {group_id!r}", exc)
    refreshed = fetch_group_representation_by_id(organization_id, group_id, admin_token=token)
    if isinstance(refreshed, dict):
        return refreshed
    payload["id"] = group_id
    return payload


def rename_group_representation(
    organization_id: str,
    group_id: str,
    group_name: str,
    *,
    mapped_role_names: list[str] | tuple[str, ...] | None = None,
    admin_token: str | None = None,
) -> dict[str, Any]:
    representation = fetch_group_representation_by_id(organization_id, group_id, admin_token=admin_token)
    if not isinstance(representation, dict):
        raise ValueError(f"Group '{group_id}' could not be found in tenant '{organization_id}'.")
    return _put_group_attributes(
        organization_id,
        group_id,
        representation,
        name=group_name,
        role_names=mapped_role_names,
        admin_token=admin_token,
    )


def set_group_role_names(
    organization_id: str,
    group_id: str,
    role_names: list[str] | tuple[str, ...],
    *,
    admin_token: str | None = None,
) -> dict[str, Any]:
    representation = fetch_group_representation_by_id(organization_id, group_id, admin_token=admin_token)
    if not isinstance(representation, dict):
        raise ValueError(f"Group '{group_id}' could not be found in tenant '{organization_id}'.")
    return _put_group_attributes(
        organization_id,
        group_id,
        representation,
        role_names=role_names,
        admin_token=admin_token,
    )


def fetch_realm_role_representation(
    realm_name: str,
    role_name: str,
    *,
    admin_token: str | None = None,
) -> dict[str, Any] | None:
    if not realm_name or not str(realm_name).strip():
        raise ValueError("realm_name is required")
    if not role_name or not str(role_name).strip():
        raise ValueError("role_name is required")
    normalized_realm = str(realm_name).strip()
    normalized_role = str(role_name).strip()
    try:
        response = requests.get(
            f"{keycloak_url()}/admin/realms/{quote(normalized_realm, safe='')}/roles/{quote(normalized_role, safe='')}",
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise _unavailable(f"look up realm role {normalized_role!r}", exc)
    return payload if isinstance(payload, dict) else None


def list_group_realm_role_mappings(
    group_id: str,
    *,
    organization_id: str | None = None,
    admin_token: str | None = None,
) -> list[dict[str, Any]]:
    if not group_id or not str(group_id).strip():
        raise ValueError("group_id is required")
    normalized_group_id = str(group_id).strip()
    if organization_id and str(organization_id).strip():
        url = _role_mappings_url(str(organization_id).strip(), normalized_group_id, "composite")
    else:
        url = (
            f"{keycloak_url()}/admin/realms/{shared_realm_name()}/groups/"
            f"{quote(normalized_group_id, safe='')}/role-mappings/realm/composite"
        )
    try:
        response = requests.get(
            url,
            headers=_headers(_admin_token(admin_token)),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise _unavailable(f"list realm-role mappings for group {normalized_group_id!r}", exc)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def add_group_realm_role_mapping(
    group_id: str,
    role_name: str,
    *,
    organization_id: str | None = None,
    admin_token: str | None = None,
) -> None:
    if not group_id or not str(group_id).strip():
        raise ValueError("group_id is required")
    if not role_name or not str(role_name).strip():
        raise ValueError("role_name is required")
    normalized_group_id = str(group_id).strip()
    normalized_role = str(role_name).strip()
    token = _admin_token(admin_token)
    existing = {
        str(item.get("name")).strip()
        for item in list_group_realm_role_mappings(
            normalized_group_id,
            organization_id=organization_id,
            admin_token=token,
        )
        if isinstance(item.get("name"), str) and str(item.get("name")).strip()
    }
    if normalized_role in existing:
        return
    role = fetch_realm_role_representation(shared_realm_name(), normalized_role, admin_token=token)
    if not isinstance(role, dict):
        raise ValueError(f"Realm role '{normalized_role}' does not exist in shared realm '{shared_realm_name()}'.")
    if organization_id and str(organization_id).strip():
        url = _role_mappings_url(str(organization_id).strip(), normalized_group_id)
    else:
        url = (
            f"{keycloak_url()}/admin/realms/{shared_realm_name()}/groups/"
            f"{quote(normalized_group_id, safe='')}/role-mappings/realm"
        )
    try:
        response = requests.post(
            url,
            json=[role],
            headers=_headers(token),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise _unavailable(f"grant realm role {normalized_role!r} to group {normalized_group_id!r}", exc)


def remove_group_realm_role_mapping(
    group_id: str,
    role_name: str,
    *,
    organization_id: str | None = None,
    admin_token: str | None = None,
) -> None:
    if not group_id or not str(group_id).strip():
        raise ValueError("group_id is required")
    if not role_name or not str(role_name).strip():
        raise ValueError("role_name is required")
    normalized_group_id = str(group_id).strip()
    normalized_role = str(role_name).strip()
    token = _admin_token(admin_token)
    existing_role = next(
        (
            item
            for item in list_group_realm_role_mappings(
                normalized_group_id,
                organization_id=organization_id,
                admin_token=token,
            )
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and str(item.get("name")).strip() == normalized_role
        ),
        None,
    )
    if not isinstance(existing_role, dict):
        return
    if organization_id and str(organization_id).strip():
        url = _role_mappings_url(str(organization_id).strip(), normalized_group_id)
    else:
        url = (
            f"{keycloak_url()}/admin/realms/{shared_realm_name()}/groups/"
            f"{quote(normalized_group_id, safe='')}/role-mappings/realm"
        )
    try:
        response = requests.delete(
            url,
            json=[existing_role],
            headers=_headers(token),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code != 404:
            response.raise_for_status()
    except requests.RequestException as exc:
        raise _unavailable(f"remove realm role {normalized_role!r} from group {normalized_group_id!r}", exc)


def ensure_group_role_mappings(
    organization_id: str,
    *,
    admin_token: str | None = None,
) -> None:
    if not organization_id or not str(organization_id).strip():
        raise ValueError("organization_id is required")
    normalized_org = str(organization_id).strip()
    token = _admin_token(admin_token)
    for group in list_group_representations(normalized_org, admin_token=token):
        group_id = group.get("id")
        group_name = group.get("name")
        if not isinstance(group_id, str) or not group_id.strip():
            continue
        if not isinstance(group_name, str) or not group_name.strip():
            continue
        existing = fetch_group_representation_by_id(normalized_org, group_id.strip(), admin_token=token) or group
        if _attribute_enabled(
            existing.get("attributes") if isinstance(existing, Mapping) else None,
            ORGANIZATION_GROUP_ROLE_MAPPING_CONFIGURED_ATTRIBUTE,
        ):
            continue
        default_roles = normalize_tenant_role_names(tenant_roles_for_organization_group(group_name.strip()))
        if not default_roles:
            continue
        set_group_role_names(normalized_org, group_id.strip(), list(default_roles), admin_token=token)


def ensure_default_groups(
    tenant_ref: TenantRef,
    *,
    group_names: tuple[str, ...] | None = None,
    admin_token: str | None = None,
) -> list[Group]:
    organization_id = _organization_id(tenant_ref, admin_token=admin_token)
    token = _admin_token(admin_token)
    ensured: list[dict[str, Any]] = []
    for group_name in group_names or default_group_identifiers():
        if not group_name or not str(group_name).strip():
            continue
        normalized_name = str(group_name).strip()
        representation = fetch_group_representation_by_name(organization_id, normalized_name, admin_token=token)
        if representation is None:
            logger.info(
                "Creating organization group '%s' in organization %s within shared realm %s",
                normalized_name,
                organization_id,
                shared_realm_name(),
            )
            representation = create_group_representation(organization_id, normalized_name, admin_token=token)
        ensured.append(representation)
    ensure_group_role_mappings(organization_id, admin_token=token)
    tenant = resolve_tenant_ref(TenantRef(id=organization_id), admin_token=token)
    return [group_from_representation(item, tenant.ref) for item in ensured]


def add_group_member_by_id(
    organization_id: str,
    group_name: str,
    member_id: str,
    *,
    admin_token: str | None = None,
) -> None:
    if not member_id or not str(member_id).strip():
        raise ValueError("member_id is required")
    normalized_org = str(organization_id).strip()
    normalized_name = str(group_name).strip()
    normalized_member = str(member_id).strip()
    token = _admin_token(admin_token)
    representation = fetch_group_representation_by_name(normalized_org, normalized_name, admin_token=token)
    if representation is None:
        representation = create_group_representation(normalized_org, normalized_name, admin_token=token)
    group_id = representation.get("id")
    if not isinstance(group_id, str) or not group_id.strip():
        raise ProviderUnavailable(f"Group {normalized_name!r} in tenant {normalized_org!r} is missing an id")
    try:
        response = requests.put(
            _groups_url(normalized_org, group_id.strip(), "members", normalized_member),
            headers=_headers(token),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code == 409:
            logger.info(
                "Organization member %s is already assigned to organization group %s in organization %s; ignoring conflict.",
                normalized_member,
                normalized_name,
                normalized_org,
            )
            return
        response.raise_for_status()
    except requests.RequestException as exc:
        raise _unavailable(f"add member {normalized_member!r} to group {normalized_name!r}", exc)


def remove_group_member_by_id(
    organization_id: str,
    group_name: str,
    member_id: str,
    *,
    admin_token: str | None = None,
) -> None:
    if not member_id or not str(member_id).strip():
        raise ValueError("member_id is required")
    normalized_org = str(organization_id).strip()
    normalized_name = str(group_name).strip()
    normalized_member = str(member_id).strip()
    token = _admin_token(admin_token)
    representation = fetch_group_representation_by_name(normalized_org, normalized_name, admin_token=token)
    if representation is None:
        return
    group_id = representation.get("id")
    if not isinstance(group_id, str) or not group_id.strip():
        return
    try:
        response = requests.delete(
            _groups_url(normalized_org, group_id.strip(), "members", normalized_member),
            headers=_headers(token),
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code != 404:
            response.raise_for_status()
    except requests.RequestException as exc:
        raise _unavailable(f"remove member {normalized_member!r} from group {normalized_name!r}", exc)


def _user_id_for_username(username: str, *, admin_token: str | None = None) -> str:
    representation = fetch_user_representation(shared_realm_name(), username, admin_token=admin_token)
    if representation is None:
        raise UserNotFound(username)
    user_id = representation.get("id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ProviderUnavailable("Directory user is missing a subject")
    return user_id.strip()


def _require_group_id(representation: dict[str, Any], group_name: str, organization_id: str) -> str:
    group_id = representation.get("id")
    if not isinstance(group_id, str) or not group_id.strip():
        raise ProviderUnavailable(f"Group {group_name!r} in tenant {organization_id!r} is missing an id")
    return group_id.strip()


def list_groups(tenant_ref: TenantRef, *, admin_token: str | None = None) -> list[Group]:
    tenant = resolve_tenant_ref(tenant_ref, admin_token=admin_token)
    organization_id = _organization_id(tenant.ref, admin_token=admin_token)
    return [
        group_from_representation(item, tenant.ref)
        for item in list_group_representations(organization_id, admin_token=admin_token)
        if isinstance(item.get("name"), str) and str(item.get("name")).strip()
    ]


def create_group(tenant_ref: TenantRef, *, identifier: str, admin_token: str | None = None) -> Group:
    tenant = resolve_tenant_ref(tenant_ref, admin_token=admin_token)
    organization_id = _organization_id(tenant.ref, admin_token=admin_token)
    representation = create_group_representation(organization_id, identifier, admin_token=admin_token)
    return group_from_representation(representation, tenant.ref)


def delete_group(group: Group, *, admin_token: str | None = None) -> None:
    if group.tenant_ref is None:
        raise ValueError("group tenant_ref is required")
    organization_id = _organization_id(group.tenant_ref, admin_token=admin_token)
    identifier = _group_identifier(group)
    representation = fetch_group_representation_by_name(organization_id, identifier, admin_token=admin_token)
    if representation is None:
        return
    delete_group_representation(
        organization_id,
        _require_group_id(representation, identifier, organization_id),
        admin_token=admin_token,
    )


def rename_group(
    group: Group,
    *,
    identifier: str,
    roles: list[str] | None = None,
    admin_token: str | None = None,
) -> Group:
    if group.tenant_ref is None:
        raise ValueError("group tenant_ref is required")
    organization_id = _organization_id(group.tenant_ref, admin_token=admin_token)
    current_name = _group_identifier(group)
    representation = fetch_group_representation_by_name(organization_id, current_name, admin_token=admin_token)
    if representation is None:
        raise ValueError(f"Group '{current_name}' could not be found in tenant '{organization_id}'.")
    updated = rename_group_representation(
        organization_id,
        _require_group_id(representation, current_name, organization_id),
        identifier,
        mapped_role_names=roles,
        admin_token=admin_token,
    )
    tenant = resolve_tenant_ref(TenantRef(id=organization_id), admin_token=admin_token)
    return group_from_representation(updated, tenant.ref)


def add_group_member(group: Group, *, username: str, admin_token: str | None = None) -> None:
    if group.tenant_ref is None:
        raise ValueError("group tenant_ref is required")
    organization_id = _organization_id(group.tenant_ref, admin_token=admin_token)
    member_id = _user_id_for_username(username, admin_token=admin_token)
    add_group_member_by_id(organization_id, _group_identifier(group), member_id, admin_token=admin_token)


def remove_group_member(group: Group, *, username: str, admin_token: str | None = None) -> None:
    if group.tenant_ref is None:
        raise ValueError("group tenant_ref is required")
    organization_id = _organization_id(group.tenant_ref, admin_token=admin_token)
    member_id = _user_id_for_username(username, admin_token=admin_token)
    remove_group_member_by_id(organization_id, _group_identifier(group), member_id, admin_token=admin_token)


def list_group_members(group: Group, *, admin_token: str | None = None) -> list[User]:
    if group.tenant_ref is None:
        raise ValueError("group tenant_ref is required")
    organization_id = _organization_id(group.tenant_ref, admin_token=admin_token)
    representation = fetch_group_representation_by_name(
        organization_id,
        _group_identifier(group),
        admin_token=admin_token,
    )
    if representation is None:
        return []
    return [
        user_from_representation(item)
        for item in list_group_member_representations(
            organization_id,
            _require_group_id(representation, _group_identifier(group), organization_id),
            admin_token=admin_token,
        )
    ]


def set_group_roles(group: Group, *, roles: list[str], admin_token: str | None = None) -> Group:
    if group.tenant_ref is None:
        raise ValueError("group tenant_ref is required")
    organization_id = _organization_id(group.tenant_ref, admin_token=admin_token)
    identifier = _group_identifier(group)
    representation = fetch_group_representation_by_name(organization_id, identifier, admin_token=admin_token)
    if representation is None:
        raise ValueError(f"Group '{identifier}' could not be found in tenant '{organization_id}'.")
    updated = set_group_role_names(
        organization_id,
        _require_group_id(representation, identifier, organization_id),
        roles,
        admin_token=admin_token,
    )
    tenant = resolve_tenant_ref(TenantRef(id=organization_id), admin_token=admin_token)
    return group_from_representation(updated, tenant.ref)


def roles_for_group(group: Group, *, admin_token: str | None = None) -> list[str]:
    if group.tenant_ref is None:
        raise ValueError("group tenant_ref is required")
    organization_id = _organization_id(group.tenant_ref, admin_token=admin_token)
    representation = fetch_group_representation_by_name(
        organization_id,
        _group_identifier(group),
        admin_token=admin_token,
    )
    return role_names_from_representation(representation)


def assign_roles(
    *,
    username: str,
    tenant_ref: TenantRef,
    roles: list[str],
    admin_token: str | None = None,
) -> None:
    organization_id = _organization_id(tenant_ref, admin_token=admin_token)
    member_id = _user_id_for_username(username, admin_token=admin_token)
    for role_name in normalize_tenant_role_names(roles):
        group_name = primary_organization_group_name_for_tenant_role(role_name)
        if group_name:
            add_group_member_by_id(organization_id, group_name, member_id, admin_token=admin_token)
