from __future__ import annotations

import logging
from typing import Any

from extensions.startup.guard import BootPhase, phase as _get_phase

# Re-export from m8flow_core so existing imports of PatchSpec / apply_patch_spec
# from this module continue to work.
from m8flow_core.patches.registry import (  # noqa: F401
    PatchSpec,
    apply_patch_spec as _core_apply_patch_spec,
    apply_patch_specs as _core_apply_patch_specs,
)


def apply_patch_spec(spec: PatchSpec, *, flask_app: Any | None = None, logger: logging.Logger | None = None) -> bool:
    return _core_apply_patch_spec(spec, flask_app=flask_app, logger=logger, phase_guard=_get_phase)


def apply_patch_specs(
    specs: tuple[PatchSpec, ...], *, flask_app: Any | None = None, logger: logging.Logger | None = None
) -> None:
    _core_apply_patch_specs(specs, flask_app=flask_app, logger=logger, phase_guard=_get_phase)


PRE_APP_PATCH_SPECS: tuple[PatchSpec, ...] = (
    PatchSpec(
        target="m8flow_backend.services.spiff_config_patch:apply",
        minimum_phase=BootPhase.PRE_BOOTSTRAP,
    ),
    PatchSpec(
        target="m8flow_backend.services.upstream_auth_defaults_patch:apply",
        minimum_phase=BootPhase.PRE_BOOTSTRAP,
    ),
    PatchSpec(
        target="m8flow_backend.services.model_override_patch:apply",
        minimum_phase=BootPhase.PRE_BOOTSTRAP,
    ),
    PatchSpec(
        target="m8flow_backend.services.openapi_merge_patch:apply",
        minimum_phase=BootPhase.PRE_BOOTSTRAP,
    ),
)


POST_APP_CORE_PATCH_SPECS: tuple[PatchSpec, ...] = (
    PatchSpec(
        target="m8flow_backend.routes.authentication_controller_patch:apply",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.file_system_service_patch:apply",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.tenant_scoping_patch:apply",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.logging_service_patch:apply",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.authorization_service_patch:apply",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.cookie_path_patch:apply_cookie_path_patch",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.celery_tenant_context_patch:apply",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.authentication_service_patch:apply_openid_discovery_patch",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.authentication_service_patch:apply_auth_token_error_patch",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.routes.authentication_controller_patch:apply_decode_token_debug_patch",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.routes.authentication_controller_patch:apply_master_realm_auth_patch",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.authentication_service_patch:apply_refresh_token_tenant_patch",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.routes.authentication_controller_patch:apply_refresh_token_tenant_patch",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.upstream_auth_defaults_patch:apply_runtime",
        minimum_phase=BootPhase.APP_CREATED,
        needs_flask_app=True,
    ),
    PatchSpec(
        target="m8flow_backend.services.generated_jwt_audience_patch:apply",
        minimum_phase=BootPhase.APP_CREATED,
    ),
    PatchSpec(
        target="m8flow_backend.services.authentication_service_patch:apply_jwks_cache_ttl_patch",
        minimum_phase=BootPhase.APP_CREATED,
    ),
)


POST_APP_EXTENSION_PATCH_SPECS: tuple[PatchSpec, ...] = (
    PatchSpec(
        target="m8flow_backend.routes.authentication_controller_patch:apply_login_tenant_patch",
        minimum_phase=BootPhase.APP_CREATED,
        needs_flask_app=True,
        optional_import=True,
    ),
    PatchSpec(
        target="m8flow_backend.services.authentication_service_patch:apply_auth_config_on_demand_patch",
        minimum_phase=BootPhase.APP_CREATED,
        optional_import=True,
    ),
    PatchSpec(
        target="m8flow_backend.services.user_service_patch:apply",
        minimum_phase=BootPhase.APP_CREATED,
        ignore_errors=True,
    ),
)


def all_patch_specs() -> tuple[PatchSpec, ...]:
    return PRE_APP_PATCH_SPECS + POST_APP_CORE_PATCH_SPECS + POST_APP_EXTENSION_PATCH_SPECS


def registered_patch_modules() -> set[str]:
    return {spec.target.split(":", 1)[0] for spec in all_patch_specs()}
