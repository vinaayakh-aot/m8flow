from __future__ import annotations

from enum import Enum


class BootPhase(str, Enum):
    PRE_BOOTSTRAP = "PRE_BOOTSTRAP"
    POST_BOOTSTRAP = "POST_BOOTSTRAP"
    APP_CREATED = "APP_CREATED"


def require_at_least(required: BootPhase, *, what: str, current_phase_fn) -> None:
    """Check that the current boot phase is at least `required`.

    Args:
        required: Minimum phase needed.
        what: Human-readable label used in the error message.
        current_phase_fn: Zero-arg callable returning the current BootPhase.
                          Pass ``extensions.startup.guard.phase`` in the app;
                          in tests you can pass a lambda.
    """
    order = {
        BootPhase.PRE_BOOTSTRAP: 0,
        BootPhase.POST_BOOTSTRAP: 1,
        BootPhase.APP_CREATED: 2,
    }
    current = current_phase_fn()
    if order[current] < order[required]:
        msg = (
            f"Startup railguard violated for '{what}'.\n"
            f"  required phase >= {required}\n"
            f"  current phase  = {current}\n"
            "This usually means a fragile module (db/models) was imported before "
            "bootstrap() completed.\n"
            "Fix: move the import inside create_application() AFTER bootstrap(), "
            "or delay it to function scope."
        )
        raise RuntimeError(msg)
