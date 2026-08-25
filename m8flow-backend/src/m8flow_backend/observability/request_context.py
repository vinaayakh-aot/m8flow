# m8flow-backend/src/m8flow_backend/observability/request_context.py
"""Per-request correlation id, propagated the same way tenant id is.

Mirrors ``m8flow_backend.tenancy``'s ContextVar + ``flask.g`` + logging.Filter
pattern: a request id is assigned once per request (or taken from an
inbound ``X-Request-Id`` header so upstream proxies/tests can pin it), stored
where both request-scoped code (``flask.g``) and background/log code
(a ``ContextVar``) can read it, and echoed back on the response so a client
can hand it to support/observability tooling to find the matching Grafana
trace and log lines.
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar, Token
from typing import Optional

from flask import Flask, Response, g, has_request_context, request

REQUEST_ID_HEADER = "X-Request-Id"

_CONTEXT_REQUEST_ID: ContextVar[Optional[str]] = ContextVar("m8flow_request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Injects the active request id into log records for uvicorn-log.yaml."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = _CONTEXT_REQUEST_ID.get()
        if not request_id and has_request_context():
            request_id = getattr(g, "m8flow_request_id", None)
        record.m8flow_request_id = request_id or "-"
        return True


def new_request_id() -> str:
    return uuid.uuid4().hex


def set_context_request_id(request_id: str | None) -> Token:
    return _CONTEXT_REQUEST_ID.set(request_id)


def reset_context_request_id(token: Token) -> None:
    _CONTEXT_REQUEST_ID.reset(token)


def get_context_request_id() -> str | None:
    """Return the active request id, or None outside of a request/task context."""
    if has_request_context():
        request_id = getattr(g, "m8flow_request_id", None)
        if request_id:
            return request_id
    return _CONTEXT_REQUEST_ID.get()


def install_request_id_middleware(app: Flask) -> None:
    """Assign every request a correlation id and make it available everywhere.

    - Reuses an inbound ``X-Request-Id`` header when present (so a
      gateway/load balancer id survives end to end), otherwise mints one.
    - Stores it on ``flask.g`` (request-scoped) and a ``ContextVar`` (so
      code running after the request context has been torn down, e.g. a
      ``teardown_request`` handler or a queued background call, can still
      tag its logs correctly).
    - Echoes it back via the ``X-Request-Id`` response header.
    """

    @app.before_request
    def _begin_request_id() -> None:
        incoming = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
        request_id = incoming or new_request_id()
        g.m8flow_request_id = request_id
        g._m8flow_request_id_token = set_context_request_id(request_id)

    @app.after_request
    def _echo_request_id(response: Response) -> Response:
        request_id = getattr(g, "m8flow_request_id", None)
        if request_id:
            response.headers.setdefault(REQUEST_ID_HEADER, request_id)
        return response

    @app.teardown_request
    def _end_request_id(_exc: BaseException | None) -> None:
        token = getattr(g, "_m8flow_request_id_token", None)
        if token is not None:
            reset_context_request_id(token)
