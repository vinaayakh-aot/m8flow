from __future__ import annotations

import logging
import os

from flask import Flask, g
from flask_cors import CORS

from m8flow_backend.authorization import install_default_policy
from m8flow_backend.auth import install_auth_middleware
from m8flow_backend.db import attach_host_timestamp_listeners, create_all, get_session_factory
from m8flow_backend.observability.request_context import install_request_id_middleware
from m8flow_backend.routes.openapi import register_openapi_routes
from m8flow_backend.secrets import install_registry_at_boot
from m8flow_backend.startup.error_handlers import register_error_handlers
from m8flow_backend.startup.logging_setup import harden_logging
from m8flow_backend.startup.process_error_guard import install_process_level_error_guards
from m8flow_backend.startup.telemetry_setup import install_telemetry
from m8flow_backend.integrations.auth import get_auth_provider
from m8flow_backend.startup.env_var_mapper import apply_m8flow_env_mapping
from m8flow_backend.startup.routes import register_root_route

# Local UI origins always allowed for credentialed browser calls (designer :6853,
# frontend :6841, Vite defaults). Env list is additive.
_DEFAULT_CORS_ORIGINS = (
    "http://localhost:6841",
    "http://127.0.0.1:6841",
    "http://localhost:6853",
    "http://127.0.0.1:6853",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

LOGGER = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    raw = (
        os.environ.get("M8FLOW_BACKEND_CORS_ALLOW_ORIGINS")
        or os.environ.get("SPIFFWORKFLOW_BACKEND_CORS_ALLOW_ORIGINS")
        or ""
    )
    origins: list[str] = list(_DEFAULT_CORS_ORIGINS)
    for part in raw.split(","):
        part = part.strip().rstrip("/")
        if not part:
            continue
        if "://" not in part:
            part = f"http://{part}"
        if part not in origins:
            origins.append(part)
    return origins


def create_app() -> Flask:
    install_process_level_error_guards()
    apply_m8flow_env_mapping()
    harden_logging()
    install_default_policy()
    install_registry_at_boot()
    attach_host_timestamp_listeners()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SESSION_SECRET_KEY") or "dev-secret"
    app.extensions["auth_provider"] = get_auth_provider()
    # Credentialed fetches from m8flow-designer/frontend require explicit origins
    # + Allow-Credentials (wildcard + credentials is illegal per the CORS spec).
    CORS(
        app,
        origins=_cors_origins(),
        supports_credentials=True,
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    install_request_id_middleware(app)
    install_telemetry(app)
    register_error_handlers(app)

    env = (os.environ.get("M8FLOW_BACKEND_ENV") or os.environ.get("SPIFFWORKFLOW_BACKEND_ENV") or "").strip()
    if env in {"unit_testing", "testing"} or os.environ.get("M8FLOW_CREATE_ALL_SCHEMA") == "1":
        create_all()

    session_factory = get_session_factory()

    @app.before_request
    def _open_session() -> None:
        g.db_session = session_factory()

    @app.teardown_request
    def _close_session(exc) -> None:
        session = getattr(g, "db_session", None)
        if session is None:
            return
        try:
            if exc is None:
                session.commit()
            else:
                session.rollback()
        except Exception:
            # A failed commit/rollback here happens after the response body has
            # already been built, so it can never reach an @app.errorhandler.
            # Log it explicitly (Grafana-visible) and fall back to rollback so a
            # half-committed session is never left open, then still close below.
            LOGGER.exception("Failed to finalize request-scoped DB session (commit=%s)", exc is None)
            try:
                session.rollback()
            except Exception:
                LOGGER.exception("Rollback after failed session finalize also failed")
        finally:
            try:
                session.close()
            except Exception:
                LOGGER.exception("Failed to close request-scoped DB session")

    install_auth_middleware(app)
    register_openapi_routes(app)

    from m8flow_backend.routes.v1 import register_v1_routes

    register_v1_routes(app)
    register_root_route(app)

    return app


def create_application():
    return create_app()


app = create_app()
