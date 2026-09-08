"""Request-time tenant binding and PostgreSQL RLS session settings.

Resolves the active tenant once per request into flask.g and the tenant
ContextVar, then applies SET LOCAL so RLS matches the old host. Cookie
`m8flow_selected_tenant` is authoritative for shared-realm sessions.

This is the request-BINDING decision (which tenant id/RLS scope this
request runs under) -- distinct from `resolve.select(...)`, the per-session
SELECTION decision (which membership + groups the login/switch flow grants).
`resolve_request_tenant` does not call `select`: it only needs membership
*presence*, not enrichment, and runs on every request.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterable

from flask import Flask, g, has_request_context, request
from sqlalchemy import event
from sqlalchemy.orm import Session

from m8flow_backend.errors import ApiError
from m8flow_backend.auth.tenant_context import (
    SELECTED_TENANT_COOKIE_NAME,
    TENANT_CLAIM,
    TENANT_SELECTION_HEADER_NAME,
    is_concrete_tenant_id,
    reset_context_tenant_id,
    set_context_tenant_id,
    tenant_id_from_selected_cookie,
    tenant_override_for_super_admin,
)

LOGGER = logging.getLogger(__name__)

_AFTER_BEGIN_REGISTERED = False

# Single source of truth: base path prefixes when no WSGI path prefix is set.
# When SPIFFWORKFLOW_BACKEND_WSGI_PATH_PREFIX is set (e.g. "/api"), we also add
# prefix + each path so both prefixed and unprefixed deployments work.
_WSGI_PATH_PREFIX = os.getenv("SPIFFWORKFLOW_BACKEND_WSGI_PATH_PREFIX", "").strip()

# Base (unprefixed) paths that are exempt from tenant context resolution.
_BASE_TENANT_CONTEXT_EXEMPT_PATH_PREFIXES: tuple[str, ...] = (
    "/.well-known",
    "/favicon.ico",
    "/v1.0/ping",
    "/v1.0/m8flow/ping",
    "/v1.0/healthy",
    "/v1.0/status",
    "/v1.0/readyz",
    "/v1.0/openapi.json",
    "/v1.0/openapi.yaml",
    "/openapi.yaml",
    "/v1.0/ui",
    "/v1.0/static",
    # Connexion serves the spec + Swagger UI under the api base path.
    "/v1.0/m8flow/openapi.json",
    "/v1.0/m8flow/openapi.yaml",
    "/v1.0/m8flow/ui",
    "/v1.0/logout",
    "/v1.0/authentication-options",
    "/v1.0/login",
    "/v1.0/refresh",
    "/v1.0/tenants/check",
    "/v1.0/m8flow/tenant-login-url",
    "/v1.0/m8flow/organization-memberships",
    "/v1.0/m8flow/tenant-realms",
    "/v1.0/m8flow/create-tenant",
    "/m8flow/create-tenant",
    "/m8flow/organization-memberships",
    # Global tenant-management endpoints are authenticated, but they do not belong to a tenant realm.
    "/v1.0/m8flow/tenants",
    "/m8flow/tenants",
    # Public invitation accept/validate endpoints: unauthenticated and not tenant-scoped at the
    # request level (the invitation row carries its own tenant id).
    "/v1.0/m8flow/invitations",
    "/m8flow/invitations",
)

# See the path-prefix rule explained above `_WSGI_PATH_PREFIX`.
TENANT_CONTEXT_EXEMPT_PATH_PREFIXES: tuple[str, ...] = (
    _BASE_TENANT_CONTEXT_EXEMPT_PATH_PREFIXES
    + (
        tuple(f"{_WSGI_PATH_PREFIX}{p}" for p in _BASE_TENANT_CONTEXT_EXEMPT_PATH_PREFIXES)
        if _WSGI_PATH_PREFIX
        else ()
    )
)

# Path suffixes for pre-login tenant selection (no tenant context required). Also included in
# TENANT_CONTEXT_EXEMPT_PATH_PREFIXES above with /v1.0 prefix.
PRE_LOGIN_TENANT_SELECTION_PATH_PREFIXES: tuple[str, ...] = ("/tenants/check", "/m8flow/tenant-login-url")

# Backward-compatible aliases while call sites migrate to clearer naming.
PUBLIC_PATH_PREFIXES = TENANT_CONTEXT_EXEMPT_PATH_PREFIXES
TENANT_PUBLIC_PATH_PREFIXES = PRE_LOGIN_TENANT_SELECTION_PATH_PREFIXES


def path_matches_prefix(path: str, prefix: str) -> bool:
    """
    True when path is exactly prefix or is a child path of prefix.

    This avoids prefix-collision bugs like `/v1.0/login_return` matching
    `/v1.0/login`.
    """
    if path == prefix:
        return True
    normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    return path.startswith(normalized_prefix)


def path_matches_any_prefix(path: str, prefixes: Iterable[str]) -> bool:
    """True when path matches any API prefix using segment-boundary semantics."""
    return any(path_matches_prefix(path, prefix) for prefix in prefixes)


def _request_uses_master_realm_without_tenant_context() -> bool:
    """Detect master-realm requests when the resolver did not tag the request."""
    if not has_request_context():
        return False

    try:
        from m8flow_backend.integrations.auth.keycloak.config import master_realm_name
        from m8flow_backend.auth.claims import (
            authentication_identifier_from_payload,
            extract_realm_from_issuer,
        )
    except Exception:
        return False

    decoded_token = getattr(g, "_m8flow_decoded_token", None)
    if not isinstance(decoded_token, dict):
        decoded_token = getattr(g, "decoded_token", None)
    if not isinstance(decoded_token, dict):
        try:
            token: str | None = getattr(g, "token", None) if isinstance(getattr(g, "token", None), str) else None
            if not token:
                auth_header = (request.headers.get("Authorization") or "").strip()
                if auth_header.startswith("Bearer ") and len(auth_header) > 7:
                    token = auth_header[7:].strip() or None
            if not token:
                token = request.cookies.get("access_token")
            if token:
                from m8flow_backend.auth import decode_auth_token

                payload = decode_auth_token(token)
                if isinstance(payload, dict):
                    decoded_token = payload
                    g._m8flow_decoded_token = payload
        except Exception:
            decoded_token = None

    if not isinstance(decoded_token, dict):
        return False

    master_realm = master_realm_name()
    authentication_identifier = authentication_identifier_from_payload(decoded_token)
    issuer_realm = extract_realm_from_issuer(decoded_token.get("iss"))
    return authentication_identifier == master_realm or issuer_realm == master_realm


def is_tenant_context_exempt_request() -> bool:
    if not has_request_context():
        return False
    return bool(
        getattr(g, "_m8flow_tenant_context_exempt_request", False)
        or getattr(g, "_m8flow_public_request", False)
        # Master-realm sign-ins, /login_return callbacks, and other
        # intentionally tenant-less requests are treated the same as
        # path-exempt requests: tenant-scoped DB queries (e.g.
        # ReferenceCacheModel.basic_query) skip the tenant filter and
        # return the global view, instead of raising "missing tenant
        # context" for users who legitimately have no tenant. That is now
        # detected by _request_uses_master_realm_without_tenant_context();
        # the ``g._m8flow_global_request`` flag below is a legacy no-op (the
        # sync global tenant resolver that set it was retired) kept as a
        # defensive hook -- see the platform-host-100 map follow-up.
        or getattr(g, "_m8flow_global_request", False)
        or _request_uses_master_realm_without_tenant_context()
    )


def is_public_request() -> bool:
    return is_tenant_context_exempt_request()


def is_super_admin_request() -> bool:
    """Zero-arg convenience wrapper over `authorization.actor_is_super_admin(g.user)`
    for the many call sites that only have request context, not a `user` in hand."""
    if not has_request_context():
        return False
    from m8flow_backend.authorization import actor_is_super_admin

    return actor_is_super_admin(getattr(g, "user", None))


def require_tenant_id(user, *, allow_super_admin_override: bool = True) -> str:
    """The one 'resolve a concrete tenant id for this request or 400' helper.
    Super-admins may select any tenant via `tenantId`/`tenant_id`
    (allow_super_admin_override); everyone else -- and a super-admin who didn't
    override -- needs the `m8flow_selected_tenant` cookie. Raises tenant_required
    (400 ApiError) if no concrete tenant resolves. Sets g.m8flow_tenant_id as a
    side effect so tenant_context.get_tenant_id() and RLS session scoping see
    the same value."""
    from m8flow_backend.authorization import actor_is_super_admin

    super_admin = actor_is_super_admin(user)
    override = tenant_override_for_super_admin(is_super_admin=super_admin) if allow_super_admin_override else None
    tenant_id = override or tenant_id_from_selected_cookie()
    if not tenant_id:
        raise ApiError("tenant_required", "m8flow_selected_tenant cookie is required", 400)
    g.m8flow_tenant_id = tenant_id
    return tenant_id


def _cookie_tenant() -> str | None:
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
    from m8flow_backend.auth.canonicalize import _canonical_tenant_id_from_identifiers

    return _canonical_tenant_id_from_identifiers(tenant_id) or tenant_id.strip()


def _payload_matches_cookie(payload: dict | None, cookie: str) -> bool:
    if not isinstance(payload, dict):
        return False
    from m8flow_backend.auth.claims import organization_memberships_from_payload
    from m8flow_backend.auth.canonicalize import current_tenant_identifiers
    from m8flow_backend.auth.identity_helpers import payload_user_belongs_to_tenant

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
    from m8flow_backend.auth.claims import tenant_id_from_payload

    claimed = tenant_id_from_payload(payload)
    if is_concrete_tenant_id(claimed):
        return claimed
    explicit = payload.get(TENANT_CLAIM)
    if isinstance(explicit, str) and is_concrete_tenant_id(explicit.strip()):
        return explicit.strip()
    return None


def _user_belongs(tenant_id: str) -> bool:
    from m8flow_backend.auth.identity_helpers import user_belongs_to_current_tenant

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

    Order: super-admin tenantId override or exempt; selected-tenant cookie
    when it matches shared-realm membership; JWT tenant claim;
    x-m8flow-tenant-id when the user belongs; cookie fallback; fail closed
    for authenticated non-exempt paths.
    """
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

    from m8flow_backend.auth.canonicalize import current_tenant_id_or_none

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
