from __future__ import annotations

import json
import logging

from m8flow_backend.observability.logging_json import JsonLogFormatter, OtelTraceFilter, build_formatter


def _make_record(level=logging.INFO, msg="hello world", exc_info=None) -> logging.LogRecord:
    return logging.LogRecord(
        name="m8flow_backend.test",
        level=level,
        pathname=__file__,
        lineno=42,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )


def test_json_formatter_produces_valid_json_with_core_fields():
    record = _make_record()
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "m8flow_backend.test"
    assert payload["service"] == "m8flow-backend"
    assert "timestamp" in payload


def test_json_formatter_includes_tenant_and_request_id_when_present():
    record = _make_record()
    record.m8flow_tenant_id = "tenant-a"
    record.m8flow_request_id = "req-123"
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["tenant_id"] == "tenant-a"
    assert payload["request_id"] == "req-123"


def test_json_formatter_omits_unset_context_placeholders():
    record = _make_record()
    record.m8flow_tenant_id = "-"
    record.m8flow_request_id = "-"
    record.otel_trace_id = "-"
    record.otel_span_id = "-"
    payload = json.loads(JsonLogFormatter().format(record))
    assert "tenant_id" not in payload
    assert "request_id" not in payload
    assert "trace_id" not in payload
    assert "span_id" not in payload


def test_json_formatter_captures_exception_details():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record(level=logging.ERROR, msg="failed", exc_info=sys.exc_info())
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["exception"]["type"] == "ValueError"
    assert payload["exception"]["message"] == "boom"
    assert "Traceback" in payload["exception"]["stacktrace"]


def test_json_formatter_nests_unknown_extra_fields():
    record = _make_record()
    record.custom_field = "custom-value"
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["extra"]["custom_field"] == "custom-value"


def test_otel_trace_filter_is_a_noop_without_an_active_span():
    record = _make_record()
    assert OtelTraceFilter().filter(record) is True
    assert record.otel_trace_id == "-"
    assert record.otel_span_id == "-"


def test_build_formatter_selects_text_via_env_var(monkeypatch):
    monkeypatch.setenv("M8FLOW_LOG_FORMAT", "text")
    formatter = build_formatter()
    assert isinstance(formatter, logging.Formatter)
    assert not isinstance(formatter, JsonLogFormatter)


def test_build_formatter_defaults_to_json(monkeypatch):
    monkeypatch.delenv("M8FLOW_LOG_FORMAT", raising=False)
    assert isinstance(build_formatter(), JsonLogFormatter)
