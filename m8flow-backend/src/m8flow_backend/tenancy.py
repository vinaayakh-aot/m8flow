from __future__ import annotations

import logging
import os
from contextvars import ContextVar, Token
from collections.abc import Iterable
from typing import Optional, cast

from flask import g, has_request_context, request

LOGGER = logging.getLogger(__name__)

# JWT claim name used to resolve tenant id. From M8FLOW_TENANT_CLAIM.
TENANT_CLAIM = (os.getenv("M8FLOW_TENANT_CLAIM") or "").strip() or "m8flow_tenant_id"

# Cookie used during shared-realm login flows to preserve the selected tenant
# across auth redirects and expired-session retries.
SELECTED_TENANT_COOKIE_NAME = "m8flow_selected_tenant"

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
    "/v1.0/openapi.json",
    "/v1.0/openapi.yaml",
    "/openapi.yaml",
    "/v1.0/ui",
    "/v1.0/static",
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

_CONTEXT_TENANT_ID: ContextVar[Optional[str]] = ContextVar("m8flow_tenant_id", default=None)


class TenantContextFilter(logging.Filter):
    """Injects tenant id into log records for uvicorn-log.yaml."""

    def filter(self, record: logging.LogRecord) -> bool:
        tenant_id = _CONTEXT_TENANT_ID.get()
        if not tenant_id and has_request_context():
            tenant_id = getattr(g, "m8flow_tenant_id", None)
        record.m8flow_tenant_id = tenant_id or "-"
        return True


# "Are we inside a request handler?" (works for ASGI/WSGI alike)
_REQUEST_ACTIVE: ContextVar[bool] = ContextVar("m8flow_request_active", default=False)

def get_healthy_response() -> tuple[dict, int]:
    """Return the canonical healthy response (payload, status_code) for reuse by health endpoints and callers."""
    return ({"status": "ok", "ok": True, "healthy": True}, 200)


def health_check():
    """Public health check for load balancers and monitoring. Returns 200 when the process is up."""
    return get_healthy_response()


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


def begin_request_context() -> Token:
    """Mark the current execution context as handling an HTTP request."""
    return _REQUEST_ACTIVE.set(True)


def end_request_context(token: Token) -> None:
    _REQUEST_ACTIVE.reset(token)


def is_request_active() -> bool:
    return _REQUEST_ACTIVE.get()


def set_context_tenant_id(tenant_id: str | None) -> Token:
    return _CONTEXT_TENANT_ID.set(tenant_id)


def reset_context_tenant_id(token: Token) -> None:
    _CONTEXT_TENANT_ID.reset(token)


def get_context_tenant_id() -> str | None:
    return _CONTEXT_TENANT_ID.get()


def is_legacy_placeholder_tenant_id(tenant_id: object) -> bool:
    """Return whether a tenant id is the legacy pre-scoping placeholder."""
    if not isinstance(tenant_id, str):
        return False
    return tenant_id.strip() == "default"


def is_concrete_tenant_id(tenant_id: object) -> bool:
    """Return whether a tenant id represents a concrete tenant context."""
    if not isinstance(tenant_id, str):
        return False

    normalized_tenant_id = tenant_id.strip()
    if not normalized_tenant_id:
        return False

    # Older migrations and requests carrying a stale request context from before
    # the current contextvar-based tenant wiring can still surface the legacy
    # placeholder value "default". Treat it the same as "public": not a usable
    # tenant-scoped runtime identifier.
    return not is_legacy_placeholder_tenant_id(normalized_tenant_id) and normalized_tenant_id != "public"


def clear_tenant_context() -> None:
    """Clear tenant context variables to prevent cross-request leakage."""
    _CONTEXT_TENANT_ID.set(None)
    if has_request_context() and hasattr(g, "_m8flow_global_request"):
        g._m8flow_global_request = False


def _request_uses_master_realm_without_tenant_context() -> bool:
    """Detect master-realm requests when the resolver did not tag the request."""
    if not has_request_context():
        return False

    try:
        from m8flow_backend.integrations.auth.keycloak.config import master_realm_name
        from m8flow_backend.services.identity_claims import (
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
        # intentionally tenant-less requests are tagged via
        # ``g._m8flow_global_request`` by the tenant resolver.  Treat them
        # the same as path-exempt requests: tenant-scoped DB queries (e.g.
        # ReferenceCacheModel.basic_query) skip the tenant filter and
        # return the global view, instead of raising "missing tenant
        # context" for users who legitimately have no tenant.
        or getattr(g, "_m8flow_global_request", False)
        or _request_uses_master_realm_without_tenant_context()
    )


def is_public_request() -> bool:
    return is_tenant_context_exempt_request()


def is_super_admin_request() -> bool:
    """Zero-arg convenience wrapper over `authorization.actor_is_super_admin(g.user)`
    for the many call sites that only have request context, not a `user` in hand.
    Previously read a `g._m8flow_super_admin_request` flag that nothing ever set
    (see architecture review finding C1) -- delegating here means the real check
    lives in exactly one place."""
    if not has_request_context():
        return False
    from m8flow_backend.authorization import actor_is_super_admin

    return actor_is_super_admin(getattr(g, "user", None))


def tenant_id_from_selected_cookie() -> str | None:
    """Read the selected-tenant cookie, or an already-resolved g.m8flow_tenant_id.
    The one place this lookup happens -- route-level tenant helpers should build
    on this instead of re-reading the cookie themselves."""
    return request.cookies.get(SELECTED_TENANT_COOKIE_NAME) or getattr(g, "m8flow_tenant_id", None)


def tenant_override_for_super_admin(*, is_super_admin: bool) -> str | None:
    """Optional cross-tenant scope override: `tenantId` or `tenant_id` query param
    (both spellings m8flow-frontend/m8flow-designer send), honored only for
    super-admins."""
    if not is_super_admin:
        return None
    return request.args.get("tenantId") or request.args.get("tenant_id") or None


def require_tenant_id(user, *, allow_super_admin_override: bool = True) -> str:
    """The one 'resolve a concrete tenant id for this request or 400' helper.
    Super-admins may select any tenant via `tenantId`/`tenant_id`
    (allow_super_admin_override); everyone else -- and a super-admin who didn't
    override -- needs the `m8flow_selected_tenant` cookie. Raises tenant_required
    (400 ApiError) if no concrete tenant resolves. Sets g.m8flow_tenant_id as a
    side effect so tenancy.get_tenant_id() and RLS session scoping see the same
    value.

    Was 3-4 independent reimplementations (routes/v1.py::_require_tenant,
    home_controller's tenant helpers, processes_controller::_require_concrete_tenant,
    nats_token_controller::_require_tenant_id) with different -- one of them
    outright broken -- super-admin-override semantics; see architecture review
    finding C3."""
    from m8flow_backend.authorization import actor_is_super_admin
    from m8flow_backend.errors import ApiError

    super_admin = actor_is_super_admin(user)
    override = tenant_override_for_super_admin(is_super_admin=super_admin) if allow_super_admin_override else None
    tenant_id = override or tenant_id_from_selected_cookie()
    if not tenant_id:
        raise ApiError("tenant_required", "m8flow_selected_tenant cookie is required", 400)
    g.m8flow_tenant_id = tenant_id
    return tenant_id


def get_tenant_id(*, warn_on_default: bool = True) -> str:
    """
    Return the tenant id for the current execution.

    ``warn_on_default`` is retained for compatibility with older call sites but
    no implicit default-tenant fallback remains.
    """
    if has_request_context():
        tid = cast(Optional[str], getattr(g, "m8flow_tenant_id", None))
        if tid:
            if get_context_tenant_id() != tid:
                _CONTEXT_TENANT_ID.set(tid)
            return tid

        ctx_tid = get_context_tenant_id()
        if ctx_tid:
            g.m8flow_tenant_id = ctx_tid
            return ctx_tid

        raise RuntimeError("Missing tenant id in request context.")

    # Non-request context
    ctx_tid = get_context_tenant_id()
    if ctx_tid:
        return ctx_tid

    raise RuntimeError("Missing tenant id in non-request context.")


def ensure_tenant_exists(tenant_id: str | None) -> None:
    """Validate that the tenant row exists; raise if missing to enforce pre-provisioning."""
    if not tenant_id:
        raise RuntimeError(
            f"Missing tenant id. Ensure the token contains {TENANT_CLAIM} (or set tenant in request context)."
        )

    from flask import g
    from m8flow_bpmn_core.models.tenant import M8flowTenantModel

    session = getattr(g, "db_session", None)
    tenant = session.get(M8flowTenantModel, tenant_id) if session is not None else None

    if tenant is None:
        raise RuntimeError(
            f"Tenant '{tenant_id}' does not exist. Create it in m8flow_tenant before using M8Flow."
        )


def create_tenant_if_not_exists(
    tenant_id: str,
    name: str | None = None,
    slug: str | None = None,
) -> None:
    """Create a tenant row if it does not exist (e.g. after creating a Keycloak realm).
    When slug is provided (e.g. realm name), it is used for M8flowTenantModel.slug;
    otherwise slug defaults to tenant_id (backward compatible).
    """
    if not tenant_id or not tenant_id.strip():
        return
    tenant_id = tenant_id.strip()
    display_name = (name or tenant_id).strip()
    slug_value = (slug or tenant_id).strip()

    from flask import g
    from m8flow_backend import identity

    session = getattr(g, "db_session", None)
    if session is None:
        from m8flow_backend.db import session_scope

        with session_scope() as scoped:
            identity.ensure_tenant(
                scoped, tenant_id=tenant_id, name=display_name, slug=slug_value
            )
        LOGGER.info("Created tenant row for tenant_id=%s name=%s slug=%s", tenant_id, display_name, slug_value)
        return
    identity.ensure_tenant(session, tenant_id=tenant_id, name=display_name, slug=slug_value)
    LOGGER.info("Created tenant row for tenant_id=%s name=%s slug=%s", tenant_id, display_name, slug_value)
