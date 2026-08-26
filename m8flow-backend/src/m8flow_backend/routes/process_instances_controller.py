from __future__ import annotations

from flask import g, request

from m8flow_backend import workflow
from m8flow_backend.auth import require_current_user
from m8flow_backend.authorization import allow_uri
from m8flow_backend.errors import ApiError
from m8flow_backend.helpers.response_helper import handle_api_errors, success_response
from m8flow_backend.tenancy import require_tenant_id

_EMPTY_PAGE = {"results": [], "pagination": {"count": 0, "total": 0, "pages": 0}}


@handle_api_errors
def list_process_instances():
    """Designer Process Instances list. Concrete tenant always required —
    same posture as Processes/Templates (`tenancy.require_tenant_id`): no
    merged all-tenant catalog for super-admins, even though nothing here
    technically forbids it. Denied callers get an empty page (200), not 403 —
    mirrors `list_process_models`'s own convention.
    """
    user = require_current_user()
    session = g.db_session
    tenant_id = require_tenant_id(user)

    if not allow_uri(user, "GET", "/v1.0/process-instances", session=session):
        return success_response(_EMPTY_PAGE, 200)

    status = request.args.get("status") or None
    search = request.args.get("search") or None
    started_by = request.args.get("started_by") or None
    sort = request.args.get("sort") or None
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = max(1, min(int(request.args.get("per_page", 25)), 100))
    except (TypeError, ValueError):
        per_page = 25

    rows, pagination = workflow.list_instances_for_designer(
        session,
        tenant_id=tenant_id,
        status=status,
        search=search,
        started_by=started_by,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    return success_response({"results": rows, "pagination": pagination}, 200)


@handle_api_errors
def list_process_instance_owners():
    """Distinct process-instance initiators for the tenant — populates the
    Process Instances list's "started by" filter dropdown. Same concrete-
    tenant + permission posture as `list_process_instances`: denied callers
    get an empty list (200), not a 403.
    """
    user = require_current_user()
    session = g.db_session
    tenant_id = require_tenant_id(user)

    if not allow_uri(user, "GET", "/v1.0/process-instances", session=session):
        return success_response({"owners": []}, 200)

    owners = workflow.list_instance_owners_for_designer(session, tenant_id=tenant_id)
    return success_response({"owners": owners}, 200)


@handle_api_errors
def get_process_instance(process_instance_id: int):
    """Designer Process Instance detail: metadata + source BPMN XML + per-
    task runtime state (for diagram highlighting). Denied or missing
    instance -> 404 (no existence-hiding distinction needed either way —
    same convention as `get_process_model`).
    """
    user = require_current_user()
    session = g.db_session
    tenant_id = require_tenant_id(user)

    if not allow_uri(
        user, "GET", f"/v1.0/process-instances/{process_instance_id}", session=session
    ):
        raise ApiError("not_found", "Process instance not found", 404)

    detail = workflow.get_instance_detail_for_designer(
        session, tenant_id=tenant_id, process_instance_id=process_instance_id
    )
    if detail is None:
        raise ApiError("not_found", "Process instance not found", 404)
    return success_response(detail, 200)
