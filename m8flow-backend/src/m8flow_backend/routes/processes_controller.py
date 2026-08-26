from __future__ import annotations

from urllib.parse import quote, unquote

from flask import Response, g, request

from m8flow_backend import catalog, workflow
from m8flow_backend.auth import require_current_user
from m8flow_backend.authorization import actor_is_super_admin, allow_uri
from m8flow_backend.errors import ApiError
from m8flow_backend.helpers.response_helper import handle_api_errors, success_response
from m8flow_backend.routes.home_controller import _optional_tenant_id, _tenant_override
from m8flow_bpmn_core.models.user import UserModel

_FILE_MIMETYPES = {
    "bpmn": "application/xml",
    "dmn": "application/xml",
    "json": "application/json",
    "md": "text/markdown",
}


def _safe_content_disposition(filename: str) -> dict[str, str]:
    """Build Content-Disposition header safe from injection (RFC 5987)."""
    safe = quote(filename, safe="")
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{safe}"}


def process_model_identifier_from_path_param(modified: str | None) -> str:
    """Colon-encoded nested ids, including a percent-encoded colon from fetch/Vite."""
    value = modified or ""
    previous = None
    while previous != value:
        previous = value
        value = unquote(value)
    return value.replace(":", "/")


def _require_concrete_tenant(*, user: UserModel) -> str:
    """Processes catalog is never all-tenants. Super-admin may pass tenantId
    (or tenant_id) or rely on the selected-tenant cookie; everyone else must
    have the cookie. Missing concrete tenant → 400.
    """
    super_admin = actor_is_super_admin(user)
    own_tenant_id = _optional_tenant_id()
    if super_admin:
        override = _tenant_override(super_admin=True)
        tenant_id = override or own_tenant_id
        if not tenant_id:
            raise ApiError(
                "tenant_required",
                "A concrete tenant is required (tenantId query or m8flow_selected_tenant cookie)",
                400,
            )
        g.m8flow_tenant_id = tenant_id
        return tenant_id
    if not own_tenant_id:
        raise ApiError("tenant_required", "m8flow_selected_tenant cookie is required", 400)
    g.m8flow_tenant_id = own_tenant_id
    return own_tenant_id


@handle_api_errors
def list_process_models():
    """Designer Processes models list. New endpoint rather than widening
    GET /v1.0/process-models (path-only JSON used by thin/MCP clients).

    Auth mirrors Home: allow_uri against GET /v1.0/process-models; denied
    callers get [] (200), not 403. Concrete tenant always required.
    """
    user = require_current_user()
    session = g.db_session
    tenant_id = _require_concrete_tenant(user=user)

    if not allow_uri(user, "GET", "/v1.0/process-models", session=session):
        return success_response([], 200)

    group = request.args.get("group") or None
    if group is not None:
        group = group.strip() or None

    run_stats = workflow.process_model_run_stats(session, tenant_id=tenant_id)
    rows = catalog.list_model_rows(tenant_id=tenant_id, group=group)
    return success_response(
        [
            {
                **row,
                "last_run_in_seconds": run_stats.get(row["id"], {}).get("last_run_in_seconds"),
                "runs_30d": run_stats.get(row["id"], {}).get("runs_30d", 0),
            }
            for row in rows
        ],
        200,
    )


@handle_api_errors
def list_process_groups():
    """Designer Process groups picker. Concrete tenant required; deny → []."""
    user = require_current_user()
    session = g.db_session
    tenant_id = _require_concrete_tenant(user=user)

    if not allow_uri(user, "GET", "/v1.0/process-groups", session=session):
        return success_response([], 200)

    run_stats = workflow.process_model_run_stats(session, tenant_id=tenant_id)
    rows = catalog.list_group_rows(tenant_id=tenant_id)
    result = []
    for row in rows:
        model_ids = catalog.list_models(row["id"], tenant_id=tenant_id)
        last_runs = [
            run_stats[mid]["last_run_in_seconds"]
            for mid in model_ids
            if mid in run_stats and run_stats[mid]["last_run_in_seconds"] is not None
        ]
        result.append(
            {
                **row,
                "last_run_in_seconds": max(last_runs) if last_runs else None,
            }
        )
    return success_response(result, 200)


@handle_api_errors
def get_process_model(modified_process_model_identifier: str):
    """Combined process-model detail for the designer detail page."""
    user = require_current_user()
    session = g.db_session
    tenant_id = _require_concrete_tenant(user=user)

    if not allow_uri(user, "GET", "/v1.0/process-models", session=session):
        raise ApiError("not_found", "Process model not found", 404)

    process_model_identifier = process_model_identifier_from_path_param(
        modified_process_model_identifier
    )
    identity = catalog.get_model_identity(
        tenant_id=tenant_id, process_model_identifier=process_model_identifier
    )
    if identity is None:
        raise ApiError("not_found", "Process model not found", 404)

    limit_raw = request.args.get("recent_limit")
    try:
        recent_limit = int(limit_raw) if limit_raw is not None else 10
    except (TypeError, ValueError):
        recent_limit = 10

    stats = workflow.process_model_detail_stats(
        session, tenant_id=tenant_id, process_model_identifier=process_model_identifier
    )
    recent = workflow.list_recent_instances_for_process_model(
        session,
        tenant_id=tenant_id,
        process_model_identifier=process_model_identifier,
        limit=recent_limit,
    )
    files = catalog.list_model_files(
        tenant_id=tenant_id, process_model_identifier=process_model_identifier
    )
    return success_response(
        {
            **identity,
            **stats,
            "recent_instances": recent,
            "files": files,
        },
        200,
    )


@handle_api_errors
def get_process_model_file(modified_process_model_identifier: str, file_name: str):
    """Raw content of one named file (.bpmn/.dmn/etc.) inside a process model.

    Auth/tenant gating mirrors get_process_model: denied or missing model ->
    404 (no distinction, same as the detail endpoint — avoids confirming a
    tenant-scoped model's existence to a caller who can't read it).
    """
    user = require_current_user()
    session = g.db_session
    tenant_id = _require_concrete_tenant(user=user)

    if not allow_uri(user, "GET", "/v1.0/process-models", session=session):
        raise ApiError("not_found", "Process model not found", 404)

    process_model_identifier = process_model_identifier_from_path_param(
        modified_process_model_identifier
    )
    if not catalog.model_exists(tenant_id=tenant_id, process_model_identifier=process_model_identifier):
        raise ApiError("not_found", "Process model not found", 404)

    catalog.validate_leaf_file_name(file_name)
    content = catalog.read_model_file(
        tenant_id=tenant_id, process_model_identifier=process_model_identifier, file_name=file_name
    )
    if content is None:
        raise ApiError("not_found", f"File not found: {file_name}", 404)

    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    mime = _FILE_MIMETYPES.get(extension, "application/octet-stream")
    return Response(content, mimetype=mime, headers=_safe_content_disposition(file_name))


@handle_api_errors
def put_process_model_file(modified_process_model_identifier: str, file_name: str):
    """Save one named file's bytes into an existing process model directory.

    .bpmn content is re-imported (same as catalog.save) so the process
    definition stays in sync; every file type is git-committed. Denied ->
    403 (a write op, unlike the read endpoints' 404-for-denied — there is
    nothing tenant-identity-revealing to protect by hiding the model here).
    """
    user = require_current_user()
    session = g.db_session
    tenant_id = _require_concrete_tenant(user=user)

    if not allow_uri(user, "PUT", "/v1.0/process-models", session=session):
        raise ApiError("permission_denied", "Not permitted to modify this process model", 403)

    process_model_identifier = process_model_identifier_from_path_param(
        modified_process_model_identifier
    )
    if not catalog.model_exists(tenant_id=tenant_id, process_model_identifier=process_model_identifier):
        raise ApiError("not_found", "Process model not found", 404)

    catalog.validate_leaf_file_name(file_name)
    content = request.get_data()
    if not content:
        raise ApiError("missing_content", "Request body is required", 400)

    path = catalog.update_file(
        {"id": process_model_identifier}, file_name, content, tenant_id=tenant_id
    )
    stat = path.stat()
    return success_response(
        {
            "name": file_name,
            "size_bytes": int(stat.st_size),
            "updated_at_in_seconds": int(stat.st_mtime),
        },
        200,
    )


@handle_api_errors
def start_process_instance(modified_process_model_identifier: str):
    """Start (create + initialize) a process instance from a model's latest
    definition — the Processes list/detail "Start" action. Write op: denied →
    403 (nothing tenant-identity-revealing to hide, same as
    put_process_model_file). Started with no submission variables; models that
    need a start form are launched empty here, same as workflow.start's own
    default.
    """
    user = require_current_user()
    session = g.db_session
    tenant_id = _require_concrete_tenant(user=user)

    if not allow_uri(user, "POST", "/v1.0/process-instances", session=session):
        raise ApiError("permission_denied", "Not permitted to start this process model", 403)

    process_model_identifier = process_model_identifier_from_path_param(
        modified_process_model_identifier
    )
    if not catalog.model_exists(tenant_id=tenant_id, process_model_identifier=process_model_identifier):
        raise ApiError("not_found", "Process model not found", 404)

    instance = workflow.start(
        session,
        tenant_id=tenant_id,
        user_id=user.id,
        process_model_identifier=process_model_identifier,
    )
    session.flush()
    return success_response(
        {
            "id": instance.id,
            "status": instance.status,
            "process_model_identifier": process_model_identifier,
        },
        201,
    )


@handle_api_errors
def delete_process_model(modified_process_model_identifier: str):
    """Delete a process model's on-disk BPMN spec (git-committed removal).
    Blocked (409) while any process instance still references the model, so
    its run history/audit rows are never orphaned — callers must remove or
    let those complete first. Write op: denied → 403.
    """
    user = require_current_user()
    session = g.db_session
    tenant_id = _require_concrete_tenant(user=user)

    if not allow_uri(user, "DELETE", "/v1.0/process-models", session=session):
        raise ApiError("permission_denied", "Not permitted to delete this process model", 403)

    process_model_identifier = process_model_identifier_from_path_param(
        modified_process_model_identifier
    )
    if not catalog.model_exists(tenant_id=tenant_id, process_model_identifier=process_model_identifier):
        raise ApiError("not_found", "Process model not found", 404)

    instance_count = workflow.count_instances_for_process_model(
        session, tenant_id=tenant_id, process_model_identifier=process_model_identifier
    )
    if instance_count > 0:
        raise ApiError(
            "process_model_has_instances",
            f"This process model has {instance_count} process instance(s) and cannot be deleted.",
            409,
        )

    catalog.delete_process_model(
        tenant_id=tenant_id, process_model_identifier=process_model_identifier
    )
    return success_response({"deleted": True, "id": process_model_identifier}, 200)
