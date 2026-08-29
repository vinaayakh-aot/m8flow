from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from m8flow_bpmn_core.models.tenant import M8flowTenantModel
from m8flow_bpmn_core.models.user import UserModel
from m8flow_backend.errors import ApiError
from m8flow_backend.models.native import ServiceAccountModel

# Distinct from NATS keys (`m8f_`) and from JWTs (typically `eyJ…`).
KEY_PREFIX = "m8sa_"
KEY_DELIMITER = "."
SERVICE_NAME = "service-account"
INTEGRATOR_ROLE = "integrator"


def _pepper() -> str:
    return os.environ.get("M8FLOW_SERVICE_ACCOUNT_PEPPER") or os.environ.get(
        "FLASK_SESSION_SECRET_KEY"
    ) or "unit-test-secret-key-32bytes-min"


def _hash_secret(secret: str) -> str:
    """HMAC-SHA256 of a high-entropy API secret. Not a password KDF."""
    return hmac.new(
        key=_pepper().encode("utf-8"),
        msg=secret.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def looks_like_api_key(token: str) -> bool:
    return token.startswith(KEY_PREFIX) and KEY_DELIMITER in token[len(KEY_PREFIX) :]


def parse_api_key(raw_key: str) -> tuple[str, str] | None:
    if not looks_like_api_key(raw_key):
        return None
    rest = raw_key[len(KEY_PREFIX) :]
    client_id, delimiter, secret = rest.partition(KEY_DELIMITER)
    if not delimiter or not client_id or not secret:
        return None
    return client_id, secret


def public_record(row: ServiceAccountModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "client_id": row.client_id,
        "created_at_in_seconds": row.created_at_in_seconds,
        "created_by_user_id": row.created_by_user_id,
    }


def list_accounts(session: Session, *, tenant_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(ServiceAccountModel)
        .where(ServiceAccountModel.m8f_tenant_id == tenant_id)
        .order_by(ServiceAccountModel.id.asc())
    ).all()
    return [public_record(row) for row in rows]


def get_account(session: Session, *, tenant_id: str, account_id: int) -> dict[str, Any]:
    row = _row_for_tenant(session, tenant_id=tenant_id, account_id=account_id)
    return public_record(row)


def create_account(
    session: Session,
    *,
    tenant_id: str,
    name: str,
    created_by: UserModel,
) -> dict[str, Any]:
    cleaned = name.strip()
    if not cleaned:
        raise ApiError("validation_error", "name is required", 400)
    if len(cleaned) > 255:
        raise ApiError("validation_error", "name is too long", 400)

    tenant = session.get(M8flowTenantModel, tenant_id)
    if tenant is None:
        raise ApiError("not_found", "Tenant not found", 404)

    from m8flow_backend import identity
    from m8flow_backend.services.tenant_identity_helpers import qualify_group_identifier

    client_id = secrets.token_hex(8)
    secret = secrets.token_urlsafe(32)
    raw_key = f"{KEY_PREFIX}{client_id}{KEY_DELIMITER}{secret}"

    machine_user = identity.ensure_user(
        session,
        username=f"sa-{client_id}",
        service=SERVICE_NAME,
        service_id=client_id,
    )
    identity.ensure_membership(session, machine_user, tenant)
    identity.sync_groups(
        session,
        user=machine_user,
        group_identifiers=[qualify_group_identifier(INTEGRATOR_ROLE, tenant_id=tenant_id)],
        tenant_id=tenant_id,
    )
    identity.import_yaml(session, tenant_id=tenant_id)

    row = ServiceAccountModel(
        client_id=client_id,
        name=cleaned,
        secret_hash=_hash_secret(secret),
        created_by_user_id=created_by.id,
        m8f_tenant_id=tenant_id,
        created_at_in_seconds=int(time.time()),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ApiError(
            "duplicate_name",
            "A service account with this name already exists for you in this tenant",
            409,
        ) from exc

    payload = public_record(row)
    payload["api_key"] = raw_key
    return payload


def revoke_account(session: Session, *, tenant_id: str, account_id: int) -> None:
    row = _row_for_tenant(session, tenant_id=tenant_id, account_id=account_id)
    session.delete(row)
    session.flush()


def authenticate_api_key(session: Session, raw_key: str) -> tuple[UserModel, str] | None:
    parsed = parse_api_key(raw_key)
    if parsed is None:
        return None
    client_id, secret = parsed
    row = session.scalars(
        select(ServiceAccountModel).where(ServiceAccountModel.client_id == client_id)
    ).first()
    if row is None:
        return None
    if not hmac.compare_digest(row.secret_hash, _hash_secret(secret)):
        return None
    from m8flow_backend import identity

    user = identity.find_user_by_service_identity(
        session, service=SERVICE_NAME, service_id=client_id
    )
    if user is None:
        return None
    return user, row.m8f_tenant_id


def _row_for_tenant(session: Session, *, tenant_id: str, account_id: int) -> ServiceAccountModel:
    row = session.scalars(
        select(ServiceAccountModel).where(
            ServiceAccountModel.id == account_id,
            ServiceAccountModel.m8f_tenant_id == tenant_id,
        )
    ).first()
    if row is None:
        raise ApiError("not_found", "Service account not found", 404)
    return row
