"""Host hooks that change how m8flow-core runs a workflow.

Every process that advances workflows must install these -- the HTTP app and
the Celery worker alike. The worker never runs ``create_app()``; before this
module it had none of them, so a scheduled job (timer start, the step after a
timer) ran service tasks against core's empty registry, without the proxy's
API key, under core's default authorization policy and without the literal
fallback for unquoted service-task parameters.
"""

from __future__ import annotations


def install_host_engine_hooks() -> None:
    """Idempotent; safe to call from create_app() and the Celery bootstrap."""
    from m8flow_backend.authorization import install_default_policy
    from m8flow_backend.connectors.proxy_auth import install_connector_proxy_client_auth
    from m8flow_backend.db import attach_host_timestamp_listeners
    from m8flow_backend.secrets import install_registry_at_boot
    from m8flow_backend.workflow.service_task_params import install_service_task_literal_fallback

    install_default_policy()
    install_connector_proxy_client_auth()
    install_registry_at_boot()
    install_service_task_literal_fallback()
    attach_host_timestamp_listeners()
