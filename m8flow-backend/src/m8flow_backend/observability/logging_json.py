"""JSON log formatting + OTel trace/span correlation for uvicorn-log.yaml.

Grafana (via Alloy/Loki) ingests container stdout, so the wire format for a
log line matters: one JSON object per line lets it be parsed without a fragile
regex, and carrying ``trace_id``/``span_id`` on every record lets Grafana jump
straight from a log line to the matching trace/span exported by
``m8flow_telemetry``, without a second correlation system.
"""
from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timezone

# Attributes every stdlib LogRecord already has. Anything else on the record
# (i.e. passed via `logger.info(..., extra={...})`) is application context and
# gets nested under "extra" in the JSON payload instead of being dropped.
_STANDARD_LOG_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "taskName",
}

# Fields already promoted to top-level JSON keys by JsonLogFormatter; keep
# them out of the "extra" bucket so they aren't duplicated.
_PROMOTED_ATTRS = {"m8flow_tenant_id", "m8flow_request_id", "otel_trace_id", "otel_span_id"}


def _service_name() -> str:
    return os.getenv("OTEL_SERVICE_NAME") or os.getenv("M8FLOW_SERVICE_NAME") or "m8flow-backend"


class JsonLogFormatter(logging.Formatter):
    """Structured, single-line JSON formatter for OTLP/Grafana log pipelines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": _service_name(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }

        tenant_id = getattr(record, "m8flow_tenant_id", None)
        if tenant_id and tenant_id != "-":
            payload["tenant_id"] = tenant_id

        request_id = getattr(record, "m8flow_request_id", None)
        if request_id and request_id != "-":
            payload["request_id"] = request_id

        trace_id = getattr(record, "otel_trace_id", None)
        if trace_id and trace_id != "-":
            payload["trace_id"] = trace_id
        span_id = getattr(record, "otel_span_id", None)
        if span_id and span_id != "-":
            payload["span_id"] = span_id

        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_value) if exc_value else None,
                "stacktrace": "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
            }
        elif record.exc_text:
            payload["exception"] = {"stacktrace": record.exc_text}

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_ATTRS and key not in _PROMOTED_ATTRS and not key.startswith("_")
        }
        if extras:
            payload["extra"] = extras

        return json.dumps(payload, default=str)


_TEXT_LOG_FORMAT = (
    "%(m8flow_tenant_id)s req=%(m8flow_request_id)s trace=%(otel_trace_id)s"
    " - %(asctime)s %(levelname)s [%(name)s] %(message)s"
)
_TEXT_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def build_formatter() -> logging.Formatter:
    """Formatter factory for uvicorn-log.yaml's ``()``-style custom object hook.

    JSON is the default (this is what Grafana/Alloy/Loki want on stdout); set
    ``M8FLOW_LOG_FORMAT=text`` for a human-readable console during local dev.
    Read once, at logging-config load time (process startup) — not something
    that needs to change mid-process.
    """
    log_format = os.getenv("M8FLOW_LOG_FORMAT", "").strip().lower()
    if log_format in {"text", "console", "plain"}:
        return logging.Formatter(_TEXT_LOG_FORMAT, datefmt=_TEXT_LOG_DATEFMT)
    return JsonLogFormatter()


class OtelTraceFilter(logging.Filter):
    """Attaches the active OTel trace_id/span_id (hex) to a log record, when a span is active.

    A no-op (leaves both fields unset) when OpenTelemetry is not installed or
    there is no active span, so this filter is always safe to chain in
    uvicorn-log.yaml regardless of whether OTEL_SDK_DISABLED is set.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.otel_trace_id = "-"
        record.otel_span_id = "-"
        try:
            from opentelemetry import trace

            span_context = trace.get_current_span().get_span_context()
            if span_context is not None and span_context.is_valid:
                record.otel_trace_id = format(span_context.trace_id, "032x")
                record.otel_span_id = format(span_context.span_id, "016x")
        except Exception:
            # Telemetry must never be able to break logging.
            pass
        return True
