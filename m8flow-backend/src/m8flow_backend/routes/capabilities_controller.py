from __future__ import annotations

from flask import g

from m8flow_backend.auth import require_current_user
from m8flow_backend.authorization import allow_uri
from m8flow_backend.helpers.response_helper import handle_api_errors, success_response


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
    """
    user = require_current_user()
    session = g.db_session
    can_manage = allow_uri(
        user, "POST", "/v1.0/process-instances", session=session
    ) or allow_uri(user, "DELETE", "/v1.0/process-models", session=session)
    return success_response({"can_manage_processes": bool(can_manage)}, 200)
