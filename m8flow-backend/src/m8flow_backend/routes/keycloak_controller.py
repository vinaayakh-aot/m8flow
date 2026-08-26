"""Keycloak API controller: tenant provisioning, tenant login, create user in
realm, organization membership lookup, and tenant lifecycle (rename/delete).
"""
from __future__ import annotations

import logging

from m8flow_backend.integrations.auth import get_auth_provider
from m8flow_backend.integrations.auth.base.errors import ProviderUnavailable, TenantNotFound, TokenInvalid
from m8flow_backend.integrations.auth.base.models import TenantRef
from m8flow_backend.integrations.auth.keycloak.config import shared_realm_name
from m8flow_backend.integrations.auth.keycloak.oidc import authorization_endpoint
from m8flow_backend.services.tenant_management_authorization import ensure_request_can_access_tenant
from m8flow_backend.services.tenant_management_authorization import require_authorized_user
from sqlalchemy.exc import IntegrityError
from m8flow_backend.errors import ApiError
from m8flow_backend.authorization import user_has_permission
from m8flow_backend.helpers.response_helper import handle_api_errors

from m8flow_backend.tenancy import create_tenant_if_not_exists
from m8flow_backend.models.m8flow_tenant import M8flowTenantModel
from m8flow_backend.services.tenant_service import TenantService
from m8flow_backend.db import db
from flask import request, g

logger = logging.getLogger(__name__)


def _requested_tenant_alias(body: dict) -> str | None:
    """Return the requested tenant alias from the legacy or org-native request payload."""
    return body.get("slug") or body.get("realm_id")


def _requested_tenant_name(body: dict) -> str | None:
    """Return the requested tenant display name from the legacy or org-native request payload."""
    return body.get("name") or body.get("display_name")


def _tenant_provisioning_response(
    *,
    organization_id: str,
    alias: str,
    name: str,
) -> dict[str, str]:
    """Return the create-tenant response while keeping legacy fields for current clients."""
    return {
        "id": organization_id,
        "organization_id": organization_id,
        "keycloak_realm_id": organization_id,
        "realm": alias,
        "alias": alias,
        "displayName": name,
        "name": name,
    }


def create_realm(body: dict) -> tuple[dict, int]:
    """Create a tenant organization in the shared realm. Returns (response_dict, status_code)."""

    user = getattr(g, 'user', None)
    if not user:
        raise ApiError(error_code="not_authenticated", message="User not authenticated", status_code=401)
    
    is_authorized = user_has_permission(user, "create", request.path)
        
    if not is_authorized:
        logger.warning(
            "User %s (groups: %s) attempted to create a tenant organization without required permissions",
            user.username, 
            [getattr(g, 'identifier', g.name) for g in getattr(user, 'groups', [])],
        )
        raise ApiError(error_code="forbidden", message="Not authorized to create a tenant.", status_code=403)


    organization_alias = _requested_tenant_alias(body)
    if not organization_alias or not str(organization_alias).strip():
        return {"detail": "realm_id or slug is required"}, 400
    organization_name = _requested_tenant_name(body)
    if organization_name and str(organization_name).strip():
        if TenantService.name_exists(str(organization_name).strip()):
            return {
                "detail": "A tenant with this name already exists. Please choose a different name.",
            }, 409
    try:
        tenant = get_auth_provider().directory_admin.create_tenant(
            alias=str(organization_alias).strip(),
            name=str(organization_name).strip() if organization_name else None,
        )
        organization_id = tenant.ref.id
        if not organization_id:
            return {"detail": "Tenant was created but is missing an id"}, 500
        alias = tenant.ref.alias or str(organization_alias).strip()
        name = tenant.display_name or alias
        create_tenant_if_not_exists(
            organization_id,
            name=name,
            slug=alias,
        )
        return _tenant_provisioning_response(
            organization_id=organization_id,
            alias=alias,
            name=name,
        ), 201
    except ProviderUnavailable as e:
        detail = str(e)
        logger.warning("Create tenant failed: %s", detail)
        if "already exists" in detail.lower():
            return {"detail": "Organization already exists or conflict"}, 409
        return {"detail": detail}, 500
    except ValueError as e:
        return {"detail": str(e)}, 400


def tenant_login(body: dict) -> tuple[dict, int]:
    """Login as a user in a spoke realm. Returns (token_response_dict, status_code)."""
    realm = body.get("realm")
    username = body.get("username")
    password = body.get("password")
    if not realm or not username:
        return {"detail": "realm and username are required"}, 400
    if password is None:
        password = ""
    try:
        result = get_auth_provider().password_grant(
            realm=str(realm).strip(),
            username=str(username),
            password=password,
        )
        return result, 200
    except TokenInvalid:
        return {"detail": "Invalid credentials"}, 401
    except ProviderUnavailable as e:
        logger.warning("Keycloak tenant login failed: %s", e)
        return {"detail": str(e)}, 500
    except ValueError as e:
        return {"detail": str(e)}, 400


def create_user_in_realm(realm: str, body: dict) -> tuple[dict, int]:
    """Create a user in a spoke realm. Returns (response_dict, status_code)."""
    username = body.get("username")
    password = body.get("password")
    if not realm or not username:
        return {"detail": "realm and username are required"}, 400
    if password is None:
        password = ""
    email = body.get("email")
    try:
        user = get_auth_provider().directory_admin.create_user(
            username=str(username).strip(),
            authentication_identifier=str(realm).strip(),
            email=str(email).strip() if email else None,
            password=password,
        )
        return {"user_id": user.subject, "location": f"/admin/realms/{realm}/users/{user.subject}"}, 201
    except ProviderUnavailable as e:
        detail = str(e)
        logger.warning("Create user failed: %s", detail)
        if "already exists" in detail.lower():
            return {"detail": "User already exists or conflict"}, 409
        return {"detail": detail}, 500
    except ValueError as e:
        return {"detail": str(e)}, 400


def get_tenant_login_url(tenant: str) -> tuple[dict, int]:
    """Validate the selected tenant and return the shared-realm login URL."""
    if not tenant or not str(tenant).strip():
        return {"detail": "tenant is required"}, 400
    tenant = str(tenant).strip()
    tenant_exists = TenantService.check_tenant_exists(tenant)
    if not tenant_exists.get("exists"):
        return {"detail": "Tenant not found"}, 404
    try:
        auth_identifier = shared_realm_name()
        login_url = authorization_endpoint(auth_identifier)
        return {
            "login_url": login_url,
            "realm": auth_identifier,
            "authentication_identifier": auth_identifier,
            "tenant_id": tenant_exists["tenant_id"],
        }, 200
    except ValueError as e:
        return {"detail": str(e)}, 400


@handle_api_errors
def get_current_user_organization_memberships() -> tuple[dict, int]:
    """Return the authenticated user's organization memberships with resolved display names."""
    session_token = request.cookies.get("access_token") or request.cookies.get("id_token")
    if not isinstance(session_token, str) or not session_token.strip():
        raise ApiError(
            error_code="not_authenticated",
            message="Authentication token not found",
            status_code=401,
        )

    try:
        claims = get_auth_provider().verify_token(session_token)
    except TokenInvalid as exc:
        raise ApiError(
            error_code="not_authenticated",
            message="Authentication token not found",
            status_code=401,
        ) from exc

    resolved_memberships: list[dict[str, str | None]] = []
    for membership in claims.memberships:
        organization_alias = membership.tenant_ref.alias or membership.tenant_ref.id or ""
        organization_id = membership.tenant_ref.id
        organization_name = membership.tenant_ref.name

        tenant = None
        if organization_id:
            tenant = (
                db.session.query(M8flowTenantModel)
                .filter(M8flowTenantModel.id == organization_id)
                .one_or_none()
            )
        if tenant is None:
            tenant = (
                db.session.query(M8flowTenantModel)
                .filter(M8flowTenantModel.slug == organization_alias)
                .one_or_none()
            )

        if tenant is not None:
            if organization_id is None:
                organization_id = tenant.id
            if organization_name is None and isinstance(tenant.name, str) and tenant.name.strip():
                organization_name = tenant.name.strip()

        resolved_memberships.append(
            {
                "alias": organization_alias,
                "id": organization_id,
                "name": organization_name,
            }
        )

    return {"organizations": resolved_memberships}, 200


def delete_tenant_realm(realm_id: str) -> tuple[dict, int]:
    """Delete a tenant organization from Keycloak and Postgres. Requires a valid admin token.
    Keycloak is deleted first; Postgres is updated only after Keycloak succeeds to avoid
    inconsistent state if Keycloak fails (network, 5xx, timeout).

    The tenant row in Postgres has FK references from tenant-scoped tables (m8f_tenant_id)
    with ON DELETE RESTRICT. If any rows still reference this tenant, the delete returns
    409 and the caller must remove or reassign those references first (or use soft delete).
    """
    user = getattr(g, 'user', None)
    if not user:
        raise ApiError(error_code="not_authenticated", message="User not authenticated", status_code=401)
    
    is_authorized = user_has_permission(user, "delete", request.path)
        
    if not is_authorized:
        logger.warning(
            "User %s (groups: %s) attempted to delete tenant %s without required permissions", 
            user.username, 
            [getattr(g, 'identifier', g.name) for g in getattr(user, 'groups', [])],
            realm_id
        )
        raise ApiError(error_code="forbidden", message="Not authorized to delete a tenant.", status_code=403)

    try:
        admin = get_auth_provider().directory_admin
        tenant = (
            db.session.query(M8flowTenantModel)
            .filter(M8flowTenantModel.slug == realm_id)
            .one_or_none()
        )
        if tenant:
            admin.delete_tenant(TenantRef(id=tenant.id, alias=tenant.slug))
        else:
            try:
                found = admin.get_tenant(TenantRef(alias=realm_id))
                admin.delete_tenant(found.ref)
            except TenantNotFound:
                logger.info(
                    "Keycloak organization with alias %s not found; deleting local tenant row if present.",
                    realm_id,
                )

        # Only after Keycloak succeeds: remove tenant from Postgres.
        if tenant:
            try:
                db.session.delete(tenant)
                db.session.commit()
                logger.info("Deleted tenant record: id=%s slug=%s", tenant.id, realm_id)
            except IntegrityError as pg_exc:
                db.session.rollback()
                logger.warning(
                    "Cannot delete tenant %s: still referenced by other tables (m8f_tenant_id). %s",
                    realm_id,
                    pg_exc,
                )
                return {
                    "detail": "Tenant cannot be deleted: it still has data in tenant-scoped tables. Remove or reassign those records first, or use soft delete (tenant status DELETED).",
                }, 409
            except Exception as pg_exc:
                db.session.rollback()
                logger.exception(
                    "Keycloak organization alias %s was deleted but Postgres delete failed; tenant record may need manual cleanup: %s",
                    realm_id,
                    pg_exc,
                )
                return {
                    "message": f"Tenant organization {realm_id} was removed from Keycloak; local tenant record may need manual cleanup.",
                }, 200
        else:
            logger.info(
                "Tenant record with slug %s not found in Postgres after Keycloak delete (already consistent).",
                realm_id,
            )

        return {"message": f"Tenant {realm_id} deleted successfully"}, 200

    except ProviderUnavailable as e:
        detail = str(e)
        logger.warning("Delete tenant failed: %s", detail)
        return {"detail": detail}, 500
    except Exception as e:
        logger.exception("Error deleting tenant %s", realm_id)
        return {"detail": str(e)}, 500


@handle_api_errors
def update_tenant_name(tenant_id: str, body: dict) -> tuple[dict, int]:
    """Update a tenant organization's display name. Requires appropriate permissions."""
    user = require_authorized_user(
        "update",
        tenant_id=tenant_id,
        forbidden_message="Not authorized to update the tenant name.",
    )

    ensure_request_can_access_tenant(
        tenant_id,
        forbidden_message="Not authorized to update another tenant.",
    )

    new_name = body.get("name")
    if not new_name or not str(new_name).strip():
        return {"detail": "name is required"}, 400
    new_name = str(new_name).strip()

    if TenantService.name_exists(new_name, exclude_tenant_id=tenant_id):
        return {
            "detail": "A tenant with this name already exists. Please choose a different name.",
        }, 409

    try:
        tenant = (
            db.session.query(M8flowTenantModel)
            .filter(M8flowTenantModel.id == tenant_id)
            .one_or_none()
        )
        if not tenant:
            return {"detail": "Tenant not found"}, 404

        get_auth_provider().directory_admin.update_tenant(
            TenantRef(id=tenant.id, alias=tenant.slug),
            name=new_name,
        )
        tenant.name = new_name
        db.session.commit()
        logger.info("Updated tenant name: id=%s slug=%s to name=%s (updated by %s)", 
                    tenant_id, tenant.slug, new_name, user.username)

        return {"message": "Tenant name updated successfully", "name": new_name}, 200

    except ProviderUnavailable as e:
        detail = str(e)
        logger.warning("Update tenant failed: %s", detail)
        return {"detail": detail}, 500
    except TenantNotFound:
        return {"detail": "Tenant not found"}, 404
    except Exception as e:
        db.session.rollback()
        logger.exception("Error updating tenant name %s", tenant_id)
        return {"detail": str(e)}, 500
