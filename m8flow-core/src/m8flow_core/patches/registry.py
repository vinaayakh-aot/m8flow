from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import logging
from typing import Any


@dataclass(frozen=True)
class PatchSpec:
    target: str
    minimum_phase: Any  # BootPhase — kept as Any to avoid circular imports
    needs_flask_app: bool = False
    optional_import: bool = False
    ignore_errors: bool = False


_APPLIED_PATCH_TARGETS: set[str] = set()


def _get_app_applied_patch_targets(flask_app: Any) -> set[str]:
    targets = getattr(flask_app, "_m8flow_applied_patch_targets", None)
    if targets is None:
        targets = set()
        setattr(flask_app, "_m8flow_applied_patch_targets", targets)
    return targets


def _resolve_patch_target(target: str):
    module_name, function_name = target.split(":", 1)
    module = import_module(module_name)
    return getattr(module, function_name), module_name, function_name


def apply_patch_spec(
    spec: PatchSpec,
    *,
    flask_app: Any | None = None,
    logger: logging.Logger | None = None,
    phase_guard=None,
) -> bool:
    """Apply a single patch spec.

    Args:
        spec: The patch to apply.
        flask_app: Required when ``spec.needs_flask_app`` is True.
        logger: Optional logger for warning messages on ignored errors.
        phase_guard: Optional zero-arg callable returning the current BootPhase.
                     When provided, the minimum-phase railguard is enforced.
                     Pass ``extensions.startup.guard.phase`` in production.
    """
    if phase_guard is not None:
        from m8flow_core.patches.boot_phase import require_at_least
        require_at_least(spec.minimum_phase, what=f"patch '{spec.target}'", current_phase_fn=phase_guard)

    target_module_name = spec.target.split(":", 1)[0]

    app_targets: set[str] | None = None
    if spec.needs_flask_app:
        if flask_app is None:
            raise RuntimeError(f"Patch '{spec.target}' requires a Flask app instance")
        app_targets = _get_app_applied_patch_targets(flask_app)
        if spec.target in app_targets:
            return False
    elif spec.target in _APPLIED_PATCH_TARGETS:
        return False

    try:
        patch_fn, _module_name, _function_name = _resolve_patch_target(spec.target)
    except ModuleNotFoundError as exc:
        if spec.optional_import and exc.name and (
            exc.name == target_module_name or target_module_name.startswith(f"{exc.name}.")
        ):
            return False
        raise

    try:
        if spec.needs_flask_app:
            patch_fn(flask_app)
        else:
            patch_fn()
    except Exception:
        if spec.ignore_errors:
            if logger is not None:
                logger.warning("Failed applying patch '%s'", spec.target, exc_info=True)
            return False
        raise

    if spec.needs_flask_app:
        assert app_targets is not None
        app_targets.add(spec.target)
    else:
        _APPLIED_PATCH_TARGETS.add(spec.target)
    return True


def apply_patch_specs(
    specs: tuple[PatchSpec, ...],
    *,
    flask_app: Any | None = None,
    logger: logging.Logger | None = None,
    phase_guard=None,
) -> None:
    for spec in specs:
        apply_patch_spec(spec, flask_app=flask_app, logger=logger, phase_guard=phase_guard)
