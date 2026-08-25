from __future__ import annotations

import os
import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from m8flow_bpmn_core.models.group import GroupModel
from m8flow_bpmn_core.models.permission_assignment import PermissionAssignmentModel
from m8flow_bpmn_core.models.permission_target import PermissionTargetModel
from m8flow_bpmn_core.models.principal import PrincipalModel
from m8flow_bpmn_core.models.tenant import M8flowTenantModel, TenantStatus
from m8flow_bpmn_core.models.user import UserModel
from m8flow_bpmn_core.models.user_group_assignment import UserGroupAssignmentModel

TIMER_SYSTEM_USERNAME = "__m8f_timer_start__"
GLOBAL_GROUP = "super-admin"

# Permission-target URI macros used in config/permissions/m8flow.yml, expanded
# to the same wildcard targets m8flow-bpmn-core seeds. Kept in sync with the
# YAML's documented macros (PM:ALL / PG:ALL).
_URI_MACROS = {
    "PM:ALL": "/process-models/%",
    "PG:ALL": "/process-groups/%",
}


def _normalize_target_uri(uri: str) -> str:
    """Match PermissionTargetModel.validate_uri: expand YAML macros and
    normalize the `*` wildcard to `%`, so lookups here find the exact rows the
    model stores (the model rewrites `*`->`%` on write; without the same
    rewrite on lookup, `grant()` misses existing rows and re-inserting collides
    on the (uri, command) unique constraint — the idempotency bug)."""
    resolved = _URI_MACROS.get(uri.strip(), uri.strip())
    return re.sub(r"\*", "%", resolved)


def ensure_tenant(
    session: Session,
    *,
    tenant_id: str,
    name: str | None = None,
    slug: str | None = None,
) -> M8flowTenantModel:
    tenant = session.get(M8flowTenantModel, tenant_id)
    if tenant is not None:
        return tenant
    tenant = session.scalars(
        select(M8flowTenantModel).where(M8flowTenantModel.slug == (slug or tenant_id))
    ).first()
    if tenant is not None:
        return tenant
    now = int(time.time())
    tenant = M8flowTenantModel(
        id=tenant_id,
        name=name or tenant_id,
        slug=slug or tenant_id,
        status=TenantStatus.ACTIVE,
        created_by="system",
        modified_by="system",
        created_at_in_seconds=now,
        updated_at_in_seconds=now,
    )
    session.add(tenant)
    session.flush()
    return tenant


def ensure_user(
    session: Session,
    *,
    username: str,
    service: str,
    service_id: str,
    email: str | None = None,
) -> UserModel:
    user = session.scalars(
        select(UserModel).where(UserModel.service == service, UserModel.service_id == service_id)
    ).first()
    if user is not None:
        return user
    if username == TIMER_SYSTEM_USERNAME:
        existing_timer = session.scalars(
            select(UserModel).where(UserModel.username == TIMER_SYSTEM_USERNAME)
        ).first()
        if existing_timer is not None:
            return existing_timer
    now = int(time.time())
    user = UserModel(
        username=username,
        email=email,
        service=service,
        service_id=service_id,
        display_name=username,
        created_at_in_seconds=now,
        updated_at_in_seconds=now,
    )
    session.add(user)
    session.flush()
    principal = PrincipalModel(user_id=user.id)
    session.add(principal)
    session.flush()
    return user


def ensure_membership(session: Session, user: UserModel, active_tenant: M8flowTenantModel) -> UserModel:
    """Replace field_1 with active tenant id and field_2 with slug when it differs."""
    user.tenant_specific_field_1 = active_tenant.id
    if active_tenant.slug and active_tenant.slug != active_tenant.id:
        user.tenant_specific_field_2 = active_tenant.slug
    else:
        user.tenant_specific_field_2 = None
    session.add(user)
    return user


def sync_groups(
    session: Session,
    *,
    user: UserModel,
    group_identifiers: list[str],
    tenant_id: str,
) -> None:
    desired: set[str] = set()
    for identifier in group_identifiers:
        normalized = identifier.strip()
        if not normalized:
            continue
        if ":" not in normalized:
            if normalized != GLOBAL_GROUP:
                continue
            desired.add(normalized)
            continue
        desired.add(normalized)

    for identifier in desired:
        group = _ensure_group(session, identifier)
        assignment = session.scalars(
            select(UserGroupAssignmentModel).where(
                UserGroupAssignmentModel.user_id == user.id,
                UserGroupAssignmentModel.group_id == group.id,
            )
        ).first()
        if assignment is None:
            session.add(UserGroupAssignmentModel(user_id=user.id, group_id=group.id))


def grant(
    session: Session,
    *,
    principal: PrincipalModel,
    uri: str,
    permission: str,
    grant_type: str = "permit",
    command: str | None = None,
) -> PermissionAssignmentModel:
    uri = _normalize_target_uri(uri)
    target = session.scalars(
        select(PermissionTargetModel).where(
            PermissionTargetModel.uri == uri,
            PermissionTargetModel.command == command,
        )
    ).first()
    if target is None:
        target = PermissionTargetModel(uri=uri, command=command)
        session.add(target)
        session.flush()
    existing = session.scalars(
        select(PermissionAssignmentModel).where(
            PermissionAssignmentModel.principal_id == principal.id,
            PermissionAssignmentModel.permission_target_id == target.id,
            PermissionAssignmentModel.permission == permission,
        )
    ).first()
    if existing is not None:
        existing.grant_type = grant_type
        return existing
    assignment = PermissionAssignmentModel(
        principal_id=principal.id,
        permission_target_id=target.id,
        permission=permission,
        grant_type=grant_type,
    )
    session.add(assignment)
    session.flush()
    return assignment


def import_yaml(session: Session | Any = None, *, tenant_id: str | None = None, yaml_path: str | None = None) -> None:
    if session is None or not hasattr(session, "get"):
        from flask import g

        from m8flow_backend.db import current_session

        session = current_session()
        tenant_id = tenant_id or getattr(g, "m8flow_tenant_id", None)
    import yaml

    path = yaml_path or os.environ.get("M8FLOW_PERMISSIONS_YAML")
    if path is None:
        path = str(
            Path_from_package()
        )
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    groups = document.get("groups") or {}
    permissions = document.get("permissions") or {}
    for group_name in groups:
        identifier = group_name if group_name == GLOBAL_GROUP else (
            f"{tenant_id}:{group_name}" if tenant_id and ":" not in group_name else group_name
        )
        if ":" not in identifier and identifier != GLOBAL_GROUP:
            continue
        _ensure_group(session, identifier)
    for _name, spec in permissions.items():
        uris = spec.get("uri")
        if isinstance(uris, str):
            uris = [uris]
        actions = spec.get("actions") or ["read"]
        command = spec.get("command")
        group_names = spec.get("groups") or []
        for group_name in group_names:
            identifier = group_name if group_name == GLOBAL_GROUP else (
                f"{tenant_id}:{group_name}" if tenant_id and ":" not in str(group_name) else str(group_name)
            )
            if identifier == "everybody" or (
                ":" not in identifier and identifier != GLOBAL_GROUP and identifier != "everybody"
            ):
                if identifier != "everybody":
                    continue
                identifier = f"{tenant_id}:user" if tenant_id else identifier
            group = _ensure_group(session, identifier)
            # Query the principal rather than reading group.principal: _ensure_group
            # already creates one for new groups, but the relationship may not be
            # populated on this instance yet, and a blind add() here duplicates it
            # (UNIQUE principal.group_id). Idempotent lookup instead.
            principal = session.scalars(
                select(PrincipalModel).where(PrincipalModel.group_id == group.id)
            ).first()
            if principal is None:
                principal = PrincipalModel(group_id=group.id)
                session.add(principal)
                session.flush()
            for uri in uris or []:
                for action in actions:
                    grant(
                        session,
                        principal=principal,
                        uri=str(uri),
                        permission=str(action),
                        command=command,
                    )
    if tenant_id:
        from m8flow_bpmn_core.services.authorization import ensure_v1_role

        ensure_v1_role(session, tenant_id=tenant_id, role_name="admin")


def allocate_lane_group_id(lane_name: str) -> int:
    from m8flow_bpmn_core.services.workflow_runtime import resolve_lane_assignment_id

    return resolve_lane_assignment_id(lane_name)


def ensure_group(session: Session | str, identifier: str | None = None, **_kwargs) -> GroupModel:
    if identifier is None or isinstance(session, str):
        from m8flow_backend.db import current_session

        identifier = session if isinstance(session, str) else identifier
        session = current_session()
    return _ensure_group(session, identifier)


def _ensure_group(session: Session, identifier: str) -> GroupModel:
    group = session.scalars(select(GroupModel).where(GroupModel.identifier == identifier)).first()
    if group is not None:
        return group
    group = GroupModel(identifier=identifier, name=identifier, source_is_open_id=True)
    session.add(group)
    session.flush()
    if group.principal is None:
        session.add(PrincipalModel(group_id=group.id))
        session.flush()
    return group


def Path_from_package() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[1] / "config" / "permissions" / "m8flow.yml")
