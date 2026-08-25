from __future__ import annotations

from flask import Flask

from m8flow_backend.routes.openapi import _adapt_view, _coerce, _flask_path


def test_coerce_treats_postponed_int_annotation_as_int():
    """Controllers use `from __future__ import annotations`, so inspect.signature
    sees the string 'int', not the type int. Postgres rejects integer = varchar
    on process_instance.id — SQLite does not."""
    assert _coerce("21", "int") == 21
    assert _coerce("21", int) == 21


def test_adapt_view_coerces_string_path_id_to_int():
    seen: dict[str, object] = {}

    def view(process_instance_id: int):
        seen["value"] = process_instance_id
        seen["cls"] = type(process_instance_id)
        return "ok"

    wrapped = _adapt_view(view)
    app = Flask(__name__)
    with app.test_request_context("/v1.0/m8flow/process-instances/21"):
        wrapped(process_instance_id="21")
    assert seen["value"] == 21
    assert seen["cls"] is int


def test_flask_path_uses_int_converter_for_int_path_params():
    path = _flask_path(
        "/v1.0/m8flow",
        "/process-instances/{process_instance_id}",
        int_params={"process_instance_id"},
    )
    assert path == "/v1.0/m8flow/process-instances/<int:process_instance_id>"
