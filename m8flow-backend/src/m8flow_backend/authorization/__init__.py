from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from m8flow_bpmn_core import api
from m8flow_bpmn_core.models.permission_assignment import PermissionAssignmentModel
from m8flow_bpmn_core.models.principal import PrincipalModel
from m8flow_bpmn_core.models.user import UserModel
from m8flow_backend.errors import ApiError
from m8flow_backend.integrations.auth.base.roles import SUPER_ADMIN_ROLE
from m8flow_backend.tenancy import is_super_admin_request


class HostAuthorizationPolicy:
    def authorize(self, session: Session, request: api.AuthorizationRequest) -> api.AuthorizationDecision:
        if _actor_is_super_admin(session, request.actor_user_id):
            return api.AuthorizationDecision(allowed=True, reason=SUPER_ADMIN_ROLE)
        default = api.DatabaseAuthorizationPolicy()
        return default.authorize(session, request)


def allow_uri(user: UserModel, method: str, path: str, *, session: Session | None = None) -> bool:
    if user is None:
        return False
    identifiers = {getattr(group, "identifier", "") for group in getattr(user, "groups", [])}
    if SUPER_ADMIN_ROLE in identifiers or is_super_admin_request():
        return True
    # Master-realm tokens carry super-admin in verified claims before local groups sync.
    # Bind to this user so a request JWT cannot elevate a different actor.
    if _verified_claims_grant_super_admin_to(user):
        return True
    action = _method_to_action(method)
    db_session = session
    if db_session is None:
        from flask import g

        db_session = getattr(g, "db_session", None)
    if db_session is None:
        return _group_identifier_fallback(user, path)
    if _uri_permitted(db_session, user, action, path):
        return True
    return _group_identifier_fallback(user, path)


def user_has_permission(user: UserModel, permission: str, path: str, *, session: Session | None = None) -> bool:
    return allow_uri(user, permission, path, session=session)


def require_authorized_user(action: str, *, forbidden_message: str, path: str | None = None) -> UserModel:
    from flask import g, request as flask_request

    from m8flow_backend.auth import require_current_user

    user = require_current_user()
    request_path = path or flask_request.path
    session = getattr(g, "db_session", None)
    if allow_uri(user, action if action in {"GET", "POST", "PUT", "DELETE"} else "GET", request_path, session=session):
        return user
    if _group_identifier_fallback(user, request_path):
        return user
    raise ApiError("permission_denied", forbidden_message, 403)


def install_default_policy() -> None:
    api.set_default_authorization_policy_factory(lambda: HostAuthorizationPolicy())


def _verified_claims_for_request():
    from m8flow_backend.integrations.auth.base.models import VerifiedClaims

    try:
        from flask import g

        claims = getattr(g, "verified_claims", None)
    except Exception:
        return None
    return claims if isinstance(claims, VerifiedClaims) else None


def _actor_matches_verified_claims(user: UserModel) -> bool:
    claims = _verified_claims_for_request()
    if claims is None:
        return False
    if user.service_id and claims.subject and str(user.service_id) == str(claims.subject):
        return True
    return bool(user.username and claims.username and user.username == claims.username)


def _verified_claims_grant_super_admin_to(user: UserModel) -> bool:
    claims = _verified_claims_for_request()
    return claims is not None and _actor_matches_verified_claims(user) and SUPER_ADMIN_ROLE in claims.roles


def _actor_is_super_admin(session: Session, user_id: int) -> bool:
    user = session.get(UserModel, user_id)
    if user is None:
        return False
    if any(getattr(group, "identifier", None) == SUPER_ADMIN_ROLE for group in user.groups):
        return True
    return _verified_claims_grant_super_admin_to(user)


def _method_to_action(method: str) -> str:
    mapping = {
        "GET": "read",
        "HEAD": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
        "read": "read",
        "create": "create",
        "update": "update",
        "delete": "delete",
        "start": "start",
    }
    return mapping.get(method.upper() if method.isupper() else method, "read")


def _uri_permitted(session: Session, user: UserModel, action: str, path: str) -> bool:
    principal_ids = [user.principal.id] if user.principal is not None else []
    group_ids = [group.id for group in user.groups]
    if group_ids:
        group_principals = session.scalars(
            select(PrincipalModel).where(PrincipalModel.group_id.in_(group_ids))
        ).all()
        principal_ids.extend(p.id for p in group_principals)
    if not principal_ids:
        return False
    assignments = session.scalars(
        select(PermissionAssignmentModel).where(
            PermissionAssignmentModel.principal_id.in_(principal_ids)
        )
    ).all()
    permitted = False
    for assignment in assignments:
        target = assignment.permission_target
        if target is None:
            continue
        if not _path_matches(path, target.uri):
            continue
        if assignment.permission not in {action, "all"}:
            continue
        if assignment.grant_type == "deny":
            return False
        permitted = True
    return permitted


def _path_matches(path: str, uri_pattern: str) -> bool:
    if uri_pattern.endswith("%"):
        return path.startswith(uri_pattern[:-1])
    return path == uri_pattern or path.startswith(uri_pattern.rstrip("/") + "/")


def _group_identifier_fallback(user: UserModel, path: str) -> bool:
    """Load-bearing for just-logged-in multi-org users before YAML grants persist."""
    identifiers = [getattr(group, "identifier", "") or "" for group in getattr(user, "groups", [])]
    if any(item == SUPER_ADMIN_ROLE or item.endswith(":tenant-admin") or item.endswith(":editor") for item in identifiers):
        return True
    if "/onboarding" in path or path.endswith("/tasks") or "/tasks" in path:
        if any(item.endswith(":reviewer") or item.endswith(":editor") or item.endswith(":user") for item in identifiers):
            return True
    return False
