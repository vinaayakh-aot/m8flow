# m8flow-backend/src/m8flow_backend/startup/error_handlers.py
"""Top-level Flask exception -> JSON response mapping.

This is the last line of defense for every request: whatever a route, a host
module, or m8flow-bpmn-core raises, the request must still end in a
structured JSON response and a logged record — never a raw Flask/Werkzeug
HTML error page, and never an exception that reaches the WSGI server
unhandled (which would otherwise surface as a bare 500 with no application
logging, or in the worst case take the worker down).

Registration order does not matter: Flask dispatches by the most specific
registered exception class in the raised exception's MRO, so ApiError,
HTTPException (Flask/Werkzeug's own 404/405/etc.), and the catch-all
Exception handler below all coexist correctly.
"""
from __future__ import annotations

import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from m8flow_backend.errors import ApiError

LOGGER = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(error: ApiError):
        _log_error(
            status_code=error.status_code,
            summary=f"ApiError {error.error_code}: {error.message}",
        )
        return jsonify({"error_code": error.error_code, "message": error.message}), error.status_code

    @app.errorhandler(HTTPException)
    def _handle_http_exception(error: HTTPException):
        status_code = error.code or 500
        error_code = (error.name or "http_error").lower().replace(" ", "_")
        message = error.description or error.name or "HTTP error"
        _log_error(status_code=status_code, summary=f"HTTPException {status_code}: {message}")
        return jsonify({"error_code": error_code, "message": message}), status_code

    @app.errorhandler(Exception)
    def _handle_unexpected_exception(error: Exception):
        # Anything reaching here is a bug (or an unmapped m8flow-bpmn-core
        # error) rather than an expected client-facing condition, so it is
        # always logged at ERROR with a full traceback regardless of status.
        _log_error(status_code=500, summary=f"Unhandled {type(error).__name__}: {error}", exc_info=True)
        return jsonify({"error_code": "internal_error", "message": "An unexpected error occurred."}), 500


def _log_error(*, status_code: int, summary: str, exc_info: bool = False) -> None:
    level = logging.ERROR if status_code >= 500 else logging.WARNING
    LOGGER.log(
        level,
        "%s %s -> %s: %s",
        request.method,
        request.path,
        status_code,
        summary,
        exc_info=exc_info or status_code >= 500,
        extra={"m8flow_status_code": status_code},
    )
