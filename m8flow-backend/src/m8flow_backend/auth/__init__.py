from __future__ import annotations

import logging
import os
import time
from typing import Any

import jwt
from flask import Flask, g, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from m8flow_bpmn_core.models.user import UserModel
from m8flow_backend.integrations.auth.keycloak.config import shared_realm_name
from m8flow_backend.errors import ApiError
from m8flow_backend.integrations.auth.base.models import Membership, VerifiedClaims
from m8flow_backend.tenancy import SELECTED_TENANT_COOKIE_NAME, get_context_tenant_id

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"


def jwt_secret() -> str:
    return os.environ.get("FLASK_SESSION_SECRET_KEY") or "unit-test-secret-key-32bytes-min"


def encode_auth_token(*, user: UserModel, extra: dict[str, Any] | None = None) -> str:
    payload = {
        "sub": f"service:{user.service}::service_id:{user.service_id}",
        "preferred_username": user.username,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400,
        "iss": user.service,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_auth_token(token: str, maybe_token: str | None = None, **_kwargs) -> dict[str, Any]:
    actual = maybe_token if maybe_token is not None else token
    try:
        header = jwt.get_unverified_header(actual)
    except jwt.PyJWTError as exc:
        raise jwt.InvalidTokenError("malformed token") from exc
    alg = header.get("alg")
    if alg == JWT_ALGORITHM:
        payload = jwt.decode(actual, jwt_secret(), algorithms=[JWT_ALGORITHM])
        _store_verified_payload(payload, verified_claims=None)
        return payload
    from m8flow_backend.integrations.auth import get_auth_provider
    from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable, TokenInvalid

    try:
        claims = get_auth_provider().verify_token(actual)
    except (TokenInvalid, ProviderUnavailable) as exc:
        raise jwt.InvalidTokenError(str(exc)) from exc
    payload = claims.jwt_claims
    if not isinstance(payload, dict):
        raise jwt.InvalidTokenError("verified token had no payload")
    _store_verified_payload(payload, verified_claims=claims)
    return payload


def _store_verified_payload(payload: dict[str, Any], *, verified_claims) -> None:
    from flask import has_request_context

    if not has_request_context():
        return
    g.decoded_token = payload
    if verified_claims is not None:
        g.verified_claims = verified_claims


def authentication_identifier_for_request() -> str:
    """Both the "original" branch and the realm-hint cookie are effectively
    unused today: `g.original_authentication_identifier` is never assigned
    anywhere in this codebase (only read here), and the `m8flow_auth_realm`
    cookie is dead (see clear_dead_auth_realm_cookie). This function
    currently always falls through to shared_realm_name().
    """
    original = getattr(g, "original_authentication_identifier", None)
    if isinstance(original, str) and original.strip():
        return original.strip()
    realm_hint = request.cookies.get("m8flow_auth_realm") if request else None
    if isinstance(realm_hint, str) and realm_hint.strip():
        return realm_hint.strip()
    return shared_realm_name()


def clear_dead_auth_realm_cookie(response) -> None:
    response.set_cookie("m8flow_auth_realm", "", max_age=0, path="/")


def set_selected_tenant_cookie(response, tenant_id: str) -> None:
    response.set_cookie(SELECTED_TENANT_COOKIE_NAME, tenant_id, max_age=86400 * 30, path="/")


def on_login_or_token_enrichment(
    session: Session,
    *,
    username: str,
    service: str,
    service_id: str,
    email: str | None,
    active_tenant_id: str,
) -> UserModel:
    from m8flow_backend import identity

    user = identity.ensure_user(
        session,
        username=username,
        service=service,
        service_id=service_id,
        email=email,
    )
    tenant = identity.ensure_tenant(session, tenant_id=active_tenant_id)
    identity.ensure_membership(session, user, tenant)
    return user


def user_from_internal_token(session: Session, decoded: dict[str, Any]) -> UserModel | None:
    subject = decoded.get("sub")
    if not isinstance(subject, str) or "::" not in subject:
        return None
    service_part, service_id_part = subject.split("::", 1)
    if not service_part.startswith("service:") or not service_id_part.startswith("service_id:"):
        return None
    service = service_part.removeprefix("service:").strip()
    service_id = service_id_part.removeprefix("service_id:").strip()
    return session.scalars(
        select(UserModel).where(UserModel.service == service, UserModel.service_id == service_id)
    ).first()


def require_current_user() -> UserModel:
    user = getattr(g, "user", None)
    if user is None:
        raise ApiError("not_authenticated", "User not authenticated", 401)
    return user


def install_auth_middleware(app: Flask) -> None:
    @app.before_request
    def _authenticate() -> None:
        from m8flow_backend.tenancy import TENANT_CONTEXT_EXEMPT_PATH_PREFIXES

        path = request.path or ""
        if any(path.startswith(prefix) for prefix in TENANT_CONTEXT_EXEMPT_PATH_PREFIXES):
            return
        header = request.headers.get("Authorization") or ""
        token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else None
        if not token:
            token = request.cookies.get("access_token")
        if not token:
            return
        try:
            decoded = decode_auth_token(token)
        except jwt.PyJWTError:
            return
        session: Session = g.db_session
        user = user_from_internal_token(session, decoded)
        if user is None:
            from sqlalchemy.exc import IntegrityError

            username = decoded.get("preferred_username") or decoded.get("sub") or "unknown"
            service = str(decoded.get("iss") or "local")
            service_id = str(decoded.get("sub") or username)
            tenant_id = (
                request.cookies.get(SELECTED_TENANT_COOKIE_NAME)
                or get_context_tenant_id()
                or shared_realm_name()
            )
            try:
                user = on_login_or_token_enrichment(
                    session,
                    username=str(username),
                    service=service,
                    service_id=service_id,
                    email=decoded.get("email") if isinstance(decoded.get("email"), str) else None,
                    active_tenant_id=str(tenant_id),
                )
            except IntegrityError:
                # Concurrent first-hit enrichment (e.g. React StrictMode double
                # fetch) can race on the unique (service, service_id) key.
                session.rollback()
                user = session.scalars(
                    select(UserModel).where(
                        UserModel.service == service,
                        UserModel.service_id == service_id,
                    )
                ).first()
                if user is None:
                    return
            _sync_groups_from_token(session, user=user, decoded=decoded, tenant_id=str(tenant_id))
        else:
            _sync_groups_from_token(
                session,
                user=user,
                decoded=decoded,
                tenant_id=str(
                    request.cookies.get(SELECTED_TENANT_COOKIE_NAME)
                    or get_context_tenant_id()
                    or shared_realm_name()
                ),
            )
        g.user = user
        g.decoded_token = decoded


def _sync_groups_from_token(
    session: Session,
    *,
    user: UserModel,
    decoded: dict[str, Any],
    tenant_id: str,
) -> None:
    """Persist verified neutral roles onto the local user (esp. master super-admin)."""
    del decoded  # RBAC/sync reads VerifiedClaims, not raw JWT JSON.
    from m8flow_backend import identity
    from m8flow_backend.integrations.auth.base.roles import SUPER_ADMIN_ROLE, VALID_TENANT_ROLE_NAMES
    from m8flow_backend.services.tenant_identity_helpers import (
        _canonical_tenant_id_from_identifiers,
        qualify_group_identifier,
    )

    claims = getattr(g, "verified_claims", None)
    if not isinstance(claims, VerifiedClaims):
        return

    identifiers: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            identifiers.append(cleaned)

    if SUPER_ADMIN_ROLE in claims.roles:
        _add(SUPER_ADMIN_ROLE)

    membership = _membership_for_active_tenant(claims.memberships, tenant_id)
    if _active_membership_needs_enrichment(claims.memberships, membership):
        membership = _enrich_active_membership(user, tenant_id, membership, claims)

    canonical_tenant_id = (
        _canonical_tenant_id_from_identifiers(
            tenant_id,
            None if membership is None else membership.tenant_ref.id,
            None if membership is None else membership.tenant_ref.alias,
        )
        or tenant_id
    )

    if membership is not None:
        for name in [*membership.roles, *membership.groups]:
            if not isinstance(name, str) or not name.strip():
                continue
            cleaned = name.strip()
            if cleaned == SUPER_ADMIN_ROLE:
                _add(SUPER_ADMIN_ROLE)
            elif cleaned in VALID_TENANT_ROLE_NAMES:
                _add(qualify_group_identifier(cleaned, tenant_id=canonical_tenant_id))

    if not identifiers:
        return
    identity.sync_groups(
        session,
        user=user,
        group_identifiers=identifiers,
        tenant_id=str(canonical_tenant_id),
    )
    # sync_groups only creates the UserGroupAssignmentModel row; it never seeds
    # the tenant-qualified group's actual m8flow.yml permissions into the DB.
    # Without this, allow_uri's real DB-grant check (_uri_permitted) has
    # nothing to find for a freshly-synced tenant role and silently falls
    # through to _group_identifier_fallback on every request -- see
    # architecture review finding C5. import_yaml's grant() calls are
    # idempotent (existing-row lookup before insert), so re-running this on
    # every enrichment is safe, matching the same pattern
    # tenant_role_service._ensure_tenant_yaml_permissions_and_everybody_membership
    # already uses for the Keycloak-organization-member-sync path.
    identity.import_yaml(session, tenant_id=str(canonical_tenant_id))
    session.flush()
    try:
        session.expire(user, ["groups"])
    except Exception:
        # Best-effort cache invalidation only; group membership was already
        # persisted above, so a stale in-memory `user.groups` is a minor
        # inconsistency for this request, not a failed sync.
        logger.debug("Failed to expire cached user.groups after group sync", exc_info=True)


def _ref_tokens(membership: Membership) -> set[str]:
    tokens: set[str] = set()
    for value in (membership.tenant_ref.id, membership.tenant_ref.alias, membership.tenant_ref.name):
        if isinstance(value, str) and value.strip():
            tokens.add(value.strip())
    return tokens


def _membership_for_active_tenant(memberships: list[Membership], tenant_id: str) -> Membership | None:
    from m8flow_backend.services.tenant_identity_helpers import _canonical_tenant_id_from_identifiers

    wanted = {tenant_id.strip()} if tenant_id.strip() else set()
    cookie_canonical = _canonical_tenant_id_from_identifiers(tenant_id)
    if cookie_canonical:
        wanted.add(cookie_canonical)
    if not wanted:
        return None

    exact: list[Membership] = []
    canonical_hits: list[Membership] = []
    for membership in memberships:
        tokens = _ref_tokens(membership)
        if tokens & wanted:
            exact.append(membership)
            continue
        member_canonical = _canonical_tenant_id_from_identifiers(*tokens, tenant_id)
        if member_canonical and member_canonical in wanted:
            canonical_hits.append(membership)
    if exact:
        return exact[0]
    if canonical_hits:
        return canonical_hits[0]
    return None


def _active_membership_needs_enrichment(
    memberships: list[Membership],
    membership: Membership | None,
) -> bool:
    if not memberships:
        return False
    if membership is not None and (membership.roles or membership.groups):
        return False
    return True


def _enrich_active_membership(
    user: UserModel,
    tenant_id: str,
    membership: Membership | None,
    claims: VerifiedClaims,
) -> Membership | None:
    from m8flow_backend.integrations.auth import get_auth_provider
    from m8flow_backend.integrations.auth.base.errors import AuthProviderError

    username = claims.username or getattr(user, "username", None)
    if not isinstance(username, str) or not username.strip():
        return membership
    try:
        directory_memberships = get_auth_provider().list_memberships(username=username.strip())
    except AuthProviderError:
        logger.warning("Thin-token membership enrichment failed for user %s", username, exc_info=True)
        return membership
    return _membership_for_active_tenant(directory_memberships, tenant_id) or membership
