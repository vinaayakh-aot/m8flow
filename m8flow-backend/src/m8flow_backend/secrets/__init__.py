from __future__ import annotations

import os
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from m8flow_bpmn_core import api
from m8flow_bpmn_core.services.connector_proxy_service_tasks import (
    build_connector_proxy_service_task_registry,
)
from m8flow_bpmn_core.services.service_tasks import ServiceTaskRegistry
from m8flow_backend.models.native import SecretModel

SECRET_SENTINEL = re.compile(r"M8FLOW_SECRET:(?P<variable_name>\w+)")


def get_secret(session: Session, *, tenant_id: str, key: str) -> SecretModel | None:
    return session.scalars(
        select(SecretModel).where(SecretModel.m8f_tenant_id == tenant_id, SecretModel.key == key)
    ).first()


def put_secret(session: Session, *, tenant_id: str, key: str, value: str) -> SecretModel:
    row = get_secret(session, tenant_id=tenant_id, key=key)
    if row is None:
        row = SecretModel(key=key, value=value, m8f_tenant_id=tenant_id)
        session.add(row)
    else:
        row.value = value
    return row


def resolve_possibly_secret_value(session: Session, *, tenant_id: str, value: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        secret = get_secret(session, tenant_id=tenant_id, key=match.group("variable_name"))
        return secret.value if secret is not None else match.group(0)

    return SECRET_SENTINEL.sub(_replace, value)


def list_connectors(registry: ServiceTaskRegistry | None = None) -> list[dict[str, Any]]:
    active = registry or _default_registry()
    grouped: dict[str, list[str]] = {}
    for command in active.list_commands():
        grouped.setdefault(command.connector_key, []).append(command.command_name)
    return [{"name": key, "commands": commands} for key, commands in grouped.items()]


def connector_proxy_url() -> str | None:
    """Active connector-proxy base URL, or None when connectors are not configured.

    Prefers ``M8FLOW_BACKEND_CONNECTOR_PROXY_URL``; falls back to the Spiff-mapped
    name after ``apply_m8flow_env_mapping()``.
    """
    raw = (
        os.environ.get("M8FLOW_BACKEND_CONNECTOR_PROXY_URL")
        or os.environ.get("SPIFFWORKFLOW_BACKEND_CONNECTOR_PROXY_URL")
        or ""
    ).strip()
    return raw or None


def build_host_service_task_registry() -> ServiceTaskRegistry:
    """Build the host ServiceTaskRegistry from the configured connector proxy.

    When ``M8FLOW_BACKEND_CONNECTOR_PROXY_URL`` is unset, returns an empty registry
    (unit tests / hosts without connectors). When set, fetches ``GET /v1/commands``
    via core's connector-proxy client — failures raise rather than silently emptying
    the catalog.
    """
    base_url = connector_proxy_url()
    if base_url is None:
        return ServiceTaskRegistry()
    return build_connector_proxy_service_task_registry(base_url)


def install_registry_at_boot() -> None:
    api.set_default_service_task_registry_factory(build_host_service_task_registry)


def _default_registry() -> ServiceTaskRegistry:
    return build_host_service_task_registry()
