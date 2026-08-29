from __future__ import annotations

from flask import g

from m8flow_backend.auth import require_current_user
from m8flow_backend.authorization import actor_is_super_admin, allow_uri
from m8flow_backend.helpers.response_helper import handle_api_errors, success_response

_AUTH_READ_ROLES = frozenset({"integrator", "viewer", "tenant-admin"})
_AUTH_MANAGE_ROLES = frozenset({"integrator", "tenant-admin"})


def _local_role_names(user) -> set[str]:
    names: set[str] = set()
    for group in getattr(user, "groups", []) or []:
        identifier = getattr(group, "identifier", "") or ""
        if not identifier:
            continue
        if ":" in identifier:
            names.add(identifier.rsplit(":", 1)[-1])
        else:
            names.add(identifier)
    return names


@handle_api_errors
def get_capabilities():
    """UI capability hints for the current user, computed from the same
    `allow_uri` gate the routes enforce — so the designer can show/hide
    affordances without guessing at Keycloak token claims (org-derived roles
    are synced into local groups server-side and aren't reliably present in the
    token). Purely advisory: every write route still authorizes independently.

    `can_manage_processes` = may start a process instance or delete a process
    model (editor / tenant-admin / super-admin). No concrete tenant required —
    allow_uri resolves from the user's groups, so this also answers correctly
    for a super-admin in All-Tenants mode.

    Authentications flags follow `m8flow.yml` role grants (integrator /
    tenant-admin manage; viewer + those roles read), not the editor/tenant-admin
    allow_uri fallback that would otherwise light up every URI.
    """
    user = require_current_user()
    session = g.db_session
    can_manage = allow_uri(
        user, "POST", "/v1.0/process-instances", session=session
    ) or allow_uri(user, "DELETE", "/v1.0/process-models", session=session)
    roles = _local_role_names(user)
    super_admin = actor_is_super_admin(user)
    can_read_authentications = super_admin or bool(roles & _AUTH_READ_ROLES)
    can_manage_authentications = super_admin or bool(roles & _AUTH_MANAGE_ROLES)
    return success_response(
        {
            "can_manage_processes": bool(can_manage),
            "can_read_authentications": can_read_authentications,
            "can_manage_authentications": can_manage_authentications,
        },
        200,
    )
