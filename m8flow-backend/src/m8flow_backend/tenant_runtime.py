"""Request-time tenant binding and PostgreSQL RLS session settings.

Resolves the active tenant once per request into flask.g and the tenant
ContextVar, then applies SET LOCAL so RLS matches the old host. Cookie
`m8flow_selected_tenant` is authoritative for shared-realm sessions.
"""
from __future__ import annotations

import logging

from flask import Flask, g, has_request_context, request
from sqlalchemy import event
from sqlalchemy.orm import Session

from m8flow_backend.errors import ApiError
from m8flow_backend.tenancy import (
    SELECTED_TENANT_COOKIE_NAME,
    TENANT_CLAIM,
    TENANT_CONTEXT_EXEMPT_PATH_PREFIXES,
    TENANT_SELECTION_HEADER_NAME,
    is_concrete_tenant_id,
    is_super_admin_request,
    is_tenant_context_exempt_request,
    path_matches_any_prefix,
    reset_context_tenant_id,
    set_context_tenant_id,
    tenant_override_for_super_admin,
)

LOGGER = logging.getLogger(__name__)

_AFTER_BEGIN_REGISTERED = False


def _cookie_tenant() -> str | None:
    sa_tenant = getattr(g, "service_account_tenant_id", None)
    if isinstance(sa_tenant, str) and sa_tenant.strip():
        return sa_tenant.strip()
    raw = request.cookies.get(SELECTED_TENANT_COOKIE_NAME)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _header_tenant() -> str | None:
    raw = request.headers.get(TENANT_SELECTION_HEADER_NAME)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _decoded_payload() -> dict | None:
    for attr in ("decoded_token", "_m8flow_decoded_token"):
        payload = getattr(g, attr, None)
        if isinstance(payload, dict):
            return payload
    return None


def _canonical(tenant_id: str) -> str:
    from m8flow_backend.services.tenant_canonicalization import (
        _canonical_tenant_id_from_identifiers,
    )

    return _canonical_tenant_id_from_identifiers(tenant_id) or tenant_id.strip()


def _payload_matches_cookie(payload: dict | None, cookie: str) -> bool:
    if not isinstance(payload, dict):
        return False
    from m8flow_backend.services.identity_claims import organization_memberships_from_payload
    from m8flow_backend.services.tenant_canonicalization import current_tenant_identifiers
    from m8flow_backend.services.tenant_identity_helpers import payload_user_belongs_to_tenant

    selected = current_tenant_identifiers(cookie) or {cookie}
    for alias, details in organization_memberships_from_payload(payload):
        org_ids = {alias}
        org_id = details.get("id")
        if isinstance(org_id, str) and org_id.strip():
            org_ids.add(org_id.strip())
        if org_ids.intersection(selected):
            return True
    return payload_user_belongs_to_tenant(
        payload, tenant_id=cookie, tenant_identifiers=selected
    )


def _jwt_tenant(payload: dict | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    from m8flow_backend.services.identity_claims import tenant_id_from_payload

    claimed = tenant_id_from_payload(payload)
    if is_concrete_tenant_id(claimed):
        return claimed
    explicit = payload.get(TENANT_CLAIM)
    if isinstance(explicit, str) and is_concrete_tenant_id(explicit.strip()):
        return explicit.strip()
    return None


def _user_belongs(tenant_id: str) -> bool:
    from m8flow_backend.services.tenant_identity_helpers import user_belongs_to_current_tenant

    user = getattr(g, "user", None)
    if user is None:
        return False
    return user_belongs_to_current_tenant(user, tenant_id=tenant_id)


def bind_request_tenant(tenant_id: str) -> str:
    """Stamp flask.g and the ContextVar with a concrete tenant id."""
    canonical = _canonical(tenant_id)
    g.m8flow_tenant_id = canonical
    existing = getattr(g, "_m8flow_ctx_token", None)
    if existing is not None:
        try:
            reset_context_tenant_id(existing)
        except Exception:
            LOGGER.debug("Could not reset previous tenant ContextVar token", exc_info=True)
    g._m8flow_ctx_token = set_context_tenant_id(canonical)
    return canonical


def mark_tenant_exempt() -> None:
    g._m8flow_tenant_context_exempt_request = True


def _path_is_exempt() -> bool:
    path = getattr(request, "path", "") or ""
    return path_matches_any_prefix(path, TENANT_CONTEXT_EXEMPT_PATH_PREFIXES)


def resolve_request_tenant() -> None:
    """Bind the active tenant for this request, or fail closed.

    Order: service-account pin; super-admin tenantId override or exempt;
    selected-tenant cookie when it matches shared-realm membership; JWT
    tenant claim; x-m8flow-tenant-id when the user belongs; cookie fallback;
    fail closed for authenticated non-exempt paths.
    """
    if getattr(g, "service_account_tenant_id", None):
        pinned = str(g.service_account_tenant_id).strip()
        if is_concrete_tenant_id(pinned):
            bind_request_tenant(pinned)
            return

    if is_super_admin_request():
        override = tenant_override_for_super_admin(is_super_admin=True)
        if is_concrete_tenant_id(override):
            bind_request_tenant(str(override).strip())
            return
        cookie = request.cookies.get(SELECTED_TENANT_COOKIE_NAME)
        if isinstance(cookie, str) and is_concrete_tenant_id(cookie.strip()):
            bind_request_tenant(cookie.strip())
            return
        mark_tenant_exempt()
        return

    payload = _decoded_payload()
    cookie = _cookie_tenant()
    if cookie and _payload_matches_cookie(payload, cookie):
        bind_request_tenant(cookie)
        return

    jwt_tenant = _jwt_tenant(payload)
    if jwt_tenant:
        bind_request_tenant(jwt_tenant)
        return

    header = _header_tenant()
    if header:
        if not _user_belongs(header):
            raise ApiError(
                "tenant_override_forbidden",
                f"Tenant override forbidden via {TENANT_SELECTION_HEADER_NAME}; "
                "the authenticated user does not belong to that tenant.",
                400,
            )
        bind_request_tenant(header)
        return

    if cookie:
        bind_request_tenant(cookie)
        return

    if _path_is_exempt() or getattr(g, "user", None) is None:
        if _path_is_exempt():
            mark_tenant_exempt()
        return

    raise ApiError(
        "tenant_required",
        "Tenant context could not be resolved from authentication data "
        f"for path '{request.path}'.",
        400,
    )


def _exec_local(connection, sql: str, params: tuple | None = None) -> None:
    exec_driver_sql = getattr(connection, "exec_driver_sql", None)
    if callable(exec_driver_sql):
        if params is None:
            exec_driver_sql(sql)
        else:
            exec_driver_sql(sql, params)
        return

    raw = getattr(connection, "connection", connection)
    driver = getattr(raw, "driver_connection", raw)
    if driver is None:
        return
    cursor = driver.cursor()
    try:
        cursor.execute(sql, params)
    finally:
        cursor.close()


def _set_local_guc(connection, name: str, value: str) -> None:
    """Apply a transaction-local GUC the way SET LOCAL would.

    PostgreSQL ``SET`` / ``SET LOCAL`` cannot take bind parameters. psycopg3
    still emits ``$1``, the server raises SyntaxError, and the request
    transaction is aborted so every later query 500s. ``set_config(...,
    is_local=true)`` is the parameterized equivalent.
    """
    _exec_local(connection, "SELECT set_config(%s, %s, true)", (name, value))


def apply_postgres_rls(connection) -> None:
    """SET LOCAL RLS GUC values for the current PostgreSQL transaction."""
    dialect = getattr(getattr(connection, "dialect", None), "name", "")
    if dialect != "postgresql":
        return

    from m8flow_backend.services.tenant_canonicalization import current_tenant_id_or_none

    tenant_id = current_tenant_id_or_none()
    super_admin = is_super_admin_request()

    if super_admin:
        _set_local_guc(connection, "app.bypass_rls", "on")
        if tenant_id:
            _set_local_guc(connection, "app.current_tenant", tenant_id)
        return

    if is_tenant_context_exempt_request():
        return
    if not tenant_id:
        return
    _set_local_guc(connection, "app.current_tenant", tenant_id)


def apply_postgres_rls_to_request_session() -> None:
    if not has_request_context():
        return
    session = getattr(g, "db_session", None)
    if session is None:
        return
    try:
        apply_postgres_rls(session.connection())
    except Exception:
        LOGGER.debug("Could not apply PostgreSQL RLS settings on the request session", exc_info=True)
        try:
            session.rollback()
        except Exception:
            LOGGER.debug("Could not roll back after RLS GUC failure", exc_info=True)


def _on_session_after_begin(session: Session, _transaction, connection) -> None:
    apply_postgres_rls(connection)


def _register_after_begin() -> None:
    global _AFTER_BEGIN_REGISTERED
    if _AFTER_BEGIN_REGISTERED:
        return
    event.listen(Session, "after_begin", _on_session_after_begin)
    _AFTER_BEGIN_REGISTERED = True


def install_tenant_runtime(app: Flask) -> None:
    """Resolve tenant after auth and keep PostgreSQL RLS session GUCs in sync."""
    _register_after_begin()

    @app.before_request
    def _bind_request_tenant() -> None:
        resolve_request_tenant()
        apply_postgres_rls_to_request_session()

    @app.teardown_request
    def _end_request_tenant(_exc: BaseException | None) -> None:
        token = getattr(g, "_m8flow_ctx_token", None)
        if token is not None:
            reset_context_tenant_id(token)
            g._m8flow_ctx_token = None
