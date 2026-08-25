from __future__ import annotations

import inspect
import re
from functools import wraps
from importlib import import_module
from pathlib import Path
from typing import get_type_hints

import yaml
from flask import Flask, request

_HTTP = {"get", "post", "put", "patch", "delete"}
_SPEC_PATH = Path(__file__).resolve().parents[1] / "api.yml"


def register_openapi_routes(app: Flask, *, spec_path: Path | None = None, base_path: str = "/v1.0/m8flow") -> None:
    path = spec_path or _SPEC_PATH
    if not path.is_file():
        raise FileNotFoundError(f"OpenAPI spec not found: {path}")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    for raw_path, item in (document.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in _HTTP or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id.strip():
                raise RuntimeError(f"Missing operationId for {method.upper()} {raw_path}")
            resolved = _resolve_operation(operation_id)
            view = _adapt_view(resolved)
            flask_path = _flask_path(base_path, raw_path, int_params=_int_path_params(resolved))
            endpoint = operation_id.replace(".", "_") + "_" + method.lower()
            app.add_url_rule(flask_path, endpoint, view, methods=[method.upper()])


def _resolve_operation(operation_id: str):
    module_name, attr = operation_id.rsplit(".", 1)
    module = import_module(module_name)
    view = getattr(module, attr, None)
    if view is None:
        raise RuntimeError(f"Could not resolve operationId {operation_id}")
    return view


def _adapt_view(view):
    signature = inspect.signature(view)
    try:
        type_hints = get_type_hints(view)
    except Exception:
        type_hints = {}

    @wraps(view)
    def wrapped(**path_kwargs):
        kwargs = {}
        json_body = None
        for name, param in signature.parameters.items():
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            annotation = type_hints.get(name, param.annotation)
            if name in path_kwargs:
                kwargs[name] = _coerce(path_kwargs[name], annotation)
                continue
            if name in request.args:
                kwargs[name] = _coerce(request.args.get(name), annotation)
                continue
            if name == "body":
                if json_body is None:
                    json_body = request.get_json(silent=True)
                kwargs[name] = json_body if json_body is not None else {}
                continue
            if param.default is inspect.Parameter.empty:
                kwargs[name] = None
        return view(**kwargs)

    return wrapped


def _coerce(value, annotation):
    if annotation is int or annotation == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return value


def _int_path_params(view) -> set[str]:
    try:
        hints = get_type_hints(view)
    except Exception:
        return set()
    return {name for name, hint in hints.items() if hint is int}


def _flask_path(base_path: str, spec_path: str, *, int_params: set[str] | None = None) -> str:
    combined = f"{base_path.rstrip('/')}{spec_path}"
    int_names = int_params or set()

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in {"file_name", "modified_process_model_identifier"}:
            return f"<path:{name}>"
        if name == "id" or name in int_names:
            return f"<int:{name}>"
        return f"<{name}>"

    return re.sub(r"\{([^}]+)\}", _replace, combined)
