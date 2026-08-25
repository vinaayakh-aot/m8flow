from __future__ import annotations

import re
from pathlib import Path

import yaml

_HTTP = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_SPEC = Path(__file__).resolve().parents[4] / "src" / "m8flow_backend" / "api.yml"


def _norm(path: str) -> str:
    path = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", path)
    path = re.sub(r"\{[^}]+\}", "{}", path)
    return path.rstrip("/") or "/"


def test_api_yml_operations_are_registered(app):
    document = yaml.safe_load(_SPEC.read_text(encoding="utf-8"))
    flask_ops = set()
    for rule in app.url_map.iter_rules():
        for method in (rule.methods or set()) & _HTTP:
            flask_ops.add((method, _norm(rule.rule)))

    missing = []
    for raw_path, item in (document.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.upper() not in _HTTP or not isinstance(operation, dict):
                continue
            expected = ("/v1.0/m8flow" + raw_path).rstrip("/") or "/"
            if (method.upper(), _norm(expected)) not in flask_ops:
                missing.append(f"{method.upper()} {expected} ({operation.get('operationId')})")
    assert not missing, "api.yml operations missing from Flask url_map:\n" + "\n".join(missing)
